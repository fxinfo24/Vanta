"""
Vanta: Apify Data Ingestion Engine
Fetch, validate, and store Apify Facebook data
"""

import os
import json
import logging
import requests
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from .schemas import ApifyFacebookPost, ApifyFacebookPostClean, PostSummary
from .lang_detect import detect_language
from app.web.models import db, SocialMediaPost, Platform, MediaType, LanguageCode
from app.web.models.verification import ClaimType


logger = logging.getLogger("Vanta.Ingestion")


class ApifyIngestionError(Exception):
    """Apify ingestion specific errors"""
    pass


class ApifyIngestor:
    """
    Engine for ingesting Apify Facebook data
    """
    
    def __init__(self, dataset_url: Optional[str] = None, clean_mode: bool = False):
        """
        Initialize ingestor
        
        Args:
            dataset_url: Apify dataset URL (or None for default)
            clean_mode: Whether to use clean dataset format (stripped metadata)
        """
        self.dataset_url = dataset_url
        self.clean_mode = clean_mode
        
        # Default Apify dataset URL format
        if not dataset_url:
            # Example: https://api.apify.com/v2/datasets/oPQI8x1X4nfpM6l5V/items?format=json
            self.dataset_url = ""
        
    def fetch_dataset(self) -> List[Dict[str, Any]]:
        """
        Fetch dataset from Apify API
        
        Returns:
            List of raw posts
        """
        if not self.dataset_url:
            raise ApifyIngestionError("No dataset URL provided")
        
        logger.info(f"Fetching Apify dataset from {self.dataset_url}")
        
        try:
            response = requests.get(
                self.dataset_url,
                headers={"Accept": "application/json"},
                timeout=30
            )
            
            if response.status_code != 200:
                raise ApifyIngestionError(f"Apify API returned {response.status_code}: {response.text}")
            
            data = response.json()
            
            if not isinstance(data, list):
                raise ApifyIngestionError(f"Expected list of posts, got {type(data)}")
            
            logger.info(f"Successfully fetched {len(data)} posts")
            return data
            
        except requests.RequestException as e:
            raise ApifyIngestionError(f"Failed to fetch Apify data: {e}")
    
    def validate_post(self, post_data: Dict[str, Any]) -> Tuple[ApifyFacebookPost, PostSummary]:
        """
        Validate a post using Pydantic schema (Layer 1 validation)
        
        Args:
            post_data: Raw post data
            
        Returns:
            Tuple of validated post and validation summary
        """
        errors = []
        validated_post = None
        
        try:
            if self.clean_mode:
                clean_post = ApifyFacebookPostClean(**post_data)
                # Convert to full schema with inferred data
                # TODO: Get actual user info and timestamp from another source
                validated_post = clean_post.to_full_schema(
                    user_info={"id": "", "name": "Unknown", "profileUrl": ""},
                    timestamp=int(datetime.now().timestamp()),
                    postId=f"clean_{hash(clean_post.url)}"
                )
            else:
                validated_post = ApifyFacebookPost(**post_data)
            
            # Calculate quality score
            quality_score = validated_post.quality_score()
            
            # Detect language
            lang_code, lang_conf = detect_language(validated_post.text)
            
            # Check for validation errors
            if quality_score < 0.5:
                errors.append(f"Low quality score: {quality_score}")
            
            if not validated_post.postId:
                errors.append("Missing postId")
            
            summary = PostSummary(
                post_id=validated_post.postId,
                quality_score=quality_score,
                detected_language=lang_code,
                text_length=len(validated_post.text),
                has_media=bool(validated_post.media),
                timestamp=validated_post.timestamp,
                validation_errors=errors,
                is_valid=quality_score > 0.3 and len(validated_post.text) > 10
            )
            
            logger.debug(f"Post {validated_post.postId}: quality={quality_score}, lang={lang_code}")
            
            return validated_post, summary
            
        except Exception as e:
            logger.error(f"Validation failed for post: {e}")
            summary = PostSummary(
                post_id=post_data.get("postId", "unknown"),
                quality_score=0.0,
                detected_language="unknown",
                text_length=len(post_data.get("text", "")),
                has_media=bool(post_data.get("media", [])),
                timestamp=post_data.get("timestamp", None),
                validation_errors=[str(e)],
                is_valid=False
            )
            return None, summary
    
    def _determine_media_type(self, media_list: List[Dict[str, Any]]) -> MediaType:
        """
        Determine media type from Apify media list
        """
        if not media_list:
            return MediaType.TEXT
        
        for media in media_list:
            typename = media.get("__typename", "")
            if typename == "Photo":
                return MediaType.PHOTO
            elif typename == "Video":
                return MediaType.VIDEO
        
        return MediaType.OTHER
    
    def convert_to_sqlalchemy_model(self, validated_post: ApifyFacebookPost) -> SocialMediaPost:
        """
        Convert validated Apify post to SQLAlchemy model
        
        Args:
            validated_post: Validated Apify post
            
        Returns:
            SocialMediaPost model ready for database storage
        """
        # Generate unique ID
        post_id = f"{Platform.FACEBOOK.value}_{validated_post.postId}"
        
        # Determine language
        lang_code, lang_conf = detect_language(validated_post.text)
        
        # Map language code
        if lang_code == "en":
            language = LanguageCode.EN
        elif lang_code == "bn":
            language = LanguageCode.BN
        else:
            language = LanguageCode.UNKNOWN
        
        # Extract media URLs
        media_urls = []
        media_metadata = []
        for media in validated_post.media:
            if media.get("__typename") == "Photo":
                photo_url = media.get("url", "")
                if photo_url:
                    media_urls.append(photo_url)
                    media_metadata.append({
                        "type": "photo",
                        "dimensions": media.get("photo_image", {}),
                        "ocr_text": media.get("ocrText", "")
                    })
            elif media.get("__typename") == "Video":
                video_url = media.get("url", "")
                if video_url:
                    media_urls.append(video_url)
                    media_metadata.append({
                        "type": "video",
                        "duration_ms": media.get("playable_duration_in_ms"),
                        "views": validated_post.viewsCount
                    })
        
        # Parse timestamp
        created_at_platform = validated_post.time
        
        # Calculate text hash for dedup
        text_hash = hash(validated_post.text) % (2**32)
        
        # Create model — platform column is String; store the enum value
        # so Product B (Enum) and Product A (String) reads agree.
        post = SocialMediaPost(
            id=post_id,
            platform=Platform.FACEBOOK.value,
            platform_post_id=validated_post.postId,
            author_id=validated_post.user.get("id", ""),
            author_name=validated_post.user.get("name", ""),
            author_profile_url=validated_post.user.get("profileUrl", ""),
            text=validated_post.text,
            text_hash=str(text_hash),
            detected_language=language,
            detected_language_confidence=lang_conf,
            created_at_platform=created_at_platform,
            likes_count=validated_post.likes,
            comments_count=validated_post.comments,
            shares_count=validated_post.shares,
            views_count=validated_post.viewsCount,
            reaction_like_count=validated_post.reactionLikeCount,
            reaction_love_count=validated_post.reactionLoveCount,
            reaction_haha_count=validated_post.reactionHahaCount,
            reaction_wow_count=validated_post.reactionWowCount,
            reaction_sad_count=validated_post.reactionSadCount,
            reaction_angry_count=validated_post.reactionAngryCount,
            reaction_care_count=validated_post.reactionCareCount,
            media_type=self._determine_media_type(validated_post.media),
            media_urls=media_urls,
            media_metadata=media_metadata,
            post_url=validated_post.url,
            platform_profile_url=validated_post.facebookUrl,
            quality_score=validated_post.quality_score(),
            completeness_score=validated_post.quality_score(),
            timestamp_validity_score=0.8 if validated_post.timestamp else 0.0,
            # JSON-serialisable dump (datetime -> isoformat) for SQLite JSON column
            raw_data=json.loads(validated_post.model_dump_json()) if hasattr(validated_post, 'model_dump_json') else json.loads(validated_post.json(default=str))
        )
        
        return post
    
    def ingest_dataset(self, max_posts: Optional[int] = None) -> Tuple[int, int]:
        """
        Main ingestion pipeline: fetch → validate → store
        
        Args:
            max_posts: Maximum number of posts to ingest
            
        Returns:
            Tuple of (successful_count, failed_count)
        """
        # Fetch dataset
        raw_posts = self.fetch_dataset()
        
        if max_posts:
            raw_posts = raw_posts[:max_posts]
        
        successful = 0
        failed = 0
        
        logger.info(f"Processing {len(raw_posts)} posts")
        
        for i, post_data in enumerate(raw_posts):
            try:
                # Validate
                validated_post, summary = self.validate_post(post_data)
                
                if not summary.is_valid:
                    logger.warning(f"Post {summary.post_id} validation failed: {summary.validation_errors}")
                    failed += 1
                    continue
                
                # Convert to SQLAlchemy model
                post_model = self.convert_to_sqlalchemy_model(validated_post)
                
                # Check if post already exists
                existing = db.session.query(SocialMediaPost).filter_by(id=post_model.id).first()
                if existing:
                    logger.debug(f"Post {post_model.id} already exists, skipping")
                    continue
                
                # Save to database
                db.session.add(post_model)
                db.session.commit()
                
                successful += 1
                logger.debug(f"Successfully ingested post {i+1}/{len(raw_posts)}")
                
            except Exception as e:
                logger.error(f"Failed to ingest post {i+1}: {e}")
                failed += 1
        
        logger.info(f"Ingestion complete: {successful} successful, {failed} failed")
        return successful, failed
    
    def ingest_from_file(self, file_path: str, max_posts: Optional[int] = None) -> Tuple[int, int]:
        """
        Ingestion from local JSON file instead of API
        
        Args:
            file_path: Path to JSON file
            max_posts: Maximum number of posts to ingest
            
        Returns:
            Tuple of (successful_count, failed_count)
        """
        try:
            with open(file_path, 'r') as f:
                raw_posts = json.load(f)
                
            if not isinstance(raw_posts, list):
                raise ApifyIngestionError(f"Expected list of posts, got {type(raw_posts)}")
            
            logger.info(f"Loaded {len(raw_posts)} posts from file")
            
            # Temporarily override dataset method
            self.fetch_dataset = lambda: raw_posts
            
            return self.ingest_dataset(max_posts)
            
        except Exception as e:
            logger.error(f"Failed to load file {file_path}: {e}")
            return 0, 0
    
    def create_migration(self):
        """
        Create Alembic migration for verification tables
        """
        # This would be called from Alembic command line
        logger.info("Creating database tables for verification pipeline")
        from app.web.models.verification import SocialMediaPost, Claim, VerificationResult, FactCheckSource, ExternalFactCheck
        
        # The tables are already defined in models, Alembic will create them
        # when we run alembic upgrade head


def ingest_apify_dataset(dataset_url: str, clean_mode: bool = False, max_posts: Optional[int] = None):
    """
    Convenience function for ingesting Apify dataset
    """
    ingestor = ApifyIngestor(dataset_url, clean_mode)
    return ingestor.ingest_dataset(max_posts)


def ingest_from_json_file(file_path: str, max_posts: Optional[int] = None):
    """
    Convenience function for ingesting from local JSON file
    """
    ingestor = ApifyIngestor(clean_mode=False)
    return ingestor.ingest_from_file(file_path, max_posts)


# Example usage
if __name__ == "__main__":
    # Example: ingest from Apify dataset URL
    dataset_url = "https://api.apify.com/v2/datasets/oPQI8x1X4nfpM6l5V/items?format=json"
    success, failed = ingest_apify_dataset(dataset_url, max_posts=100)
    print(f"Ingested {success} posts, failed {failed}")
    
    # Example: ingest from local file
    success, failed = ingest_from_json_file("path/to/apify_data.json", max_posts=50)
    print(f"Ingested {success} posts, failed {failed}")