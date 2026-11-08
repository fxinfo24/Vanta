"""
Vanta: Ingestion Schemas (Layer 1 Validation) - Fixed Version
Pydantic schemas for Apify Facebook data validation
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
import enum


class MediaType(str, enum.Enum):
    PHOTO = "Photo"
    VIDEO = "Video"
    GENERIC = "GenericAttachmentMedia"


class PhotoMedia(BaseModel):
    """Pydantic schema for photo media"""
    thumbnail: str
    typename: str = Field(alias="__typename")
    is_media: str = Field(alias="__isMedia")
    accent_color: str = Field(alias="accent_color")
    photo_product_tags: List[str]
    photo_image: Dict[str, Any]
    url: str
    id: str
    feedback: Optional[Dict[str, Any]]
    ocr_text: Optional[str] = Field(alias="ocrText")  # OCR extracted text


class VideoMedia(BaseModel):
    """Pydantic schema for video media"""
    thumbnail: str
    typename: str = Field(alias="__typename")
    thumbnail_image: Optional[Dict[str, Any]] = Field(alias="thumbnailImage")
    id: str
    is_clipping_enabled: Optional[bool]
    live_rewind_enabled: Optional[bool]
    owner: Optional[Dict[str, Any]]
    playable_duration_in_ms: Optional[int]
    is_huddle: Optional[bool]
    url: str
    publish_time: Optional[int]  # Unix timestamp
    width: Optional[int]
    height: Optional[int]
    video_delivery_legacy_fields: Optional[Dict[str, Any]] = Field(alias="videoDeliveryLegacyFields")
    image: Optional[Dict[str, Any]]


class GenericAttachmentMedia(BaseModel):
    """Generic attachment schema"""
    typename: str = Field(alias="__typename")
    url: Optional[str]
    id: Optional[str]


class ApifyFacebookPost(BaseModel):
    """
    Pydantic schema for Apify Facebook post (raw dataset format)
    This is the FULL dataset format (not cleaned)
    """
    class Config:
        allow_population_by_field_name = True
        extra = "allow"
    facebook_url: str = Field(alias="facebookUrl")
    post_id: str = Field(alias="postId")
    page_name: str = Field(alias="pageName")
    url: str
    time: datetime  # ISO 8601 datetime
    timestamp: int  # Unix timestamp
    user: Dict[str, Any]  # user object
    collaborators: List[str]
    text: str
    likes: int
    comments: int
    shares: int
    top_reactions_count: int = Field(alias="topReactionsCount")
    media: List[Dict[str, Any]]  # array of Photo/Video/Generic
    feedback_id: Optional[str] = Field(alias="feedbackId")
    reaction_like_count: Optional[int] = Field(alias="reactionLikeCount", default=0)
    reaction_love_count: Optional[int] = Field(alias="reactionLoveCount", default=0)
    reaction_care_count: Optional[int] = Field(alias="reactionCareCount", default=0)
    reaction_sad_count: Optional[int] = Field(alias="reactionSadCount", default=0)
    reaction_haha_count: Optional[int] = Field(alias="reactionHahaCount", default=0)
    reaction_wow_count: Optional[int] = Field(alias="reactionWowCount", default=0)
    reaction_angry_count: Optional[int] = Field(alias="reactionAngryCount", default=0)
    top_level_url: Optional[str] = Field(alias="topLevelUrl")
    facebook_id: Optional[str] = Field(alias="facebookId")
    page_ad_library: Optional[Dict[str, Any]] = Field(alias="pageAdLibrary")
    input_url: Optional[str] = Field(alias="inputUrl")
    is_video: Optional[bool] = Field(alias="isVideo", default=False)
    views_count: Optional[int] = Field(alias="viewsCount", default=0)

    @validator('time')
    def parse_time(cls, v):
        """Parse ISO datetime"""
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                # Try other formats
                try:
                    return datetime.strptime(v, '%Y-%m-%dT%H:%M:%S.%fZ')
                except ValueError:
                    return datetime.strptime(v, '%Y-%m-%dT%H:%M:%SZ')
        return v

    @validator('timestamp')
    def validate_timestamp(cls, v):
        """Ensure timestamp is positive"""
        if v <= 0:
            raise ValueError('timestamp must be positive')
        return v

    @validator('text')
    def validate_text(cls, v):
        """Ensure text exists, but can be empty"""
        if v is None:
            return ""
        return v.strip()

    @validator('likes', 'comments', 'shares')
    def validate_non_negative(cls, v):
        """Ensure counts are >= 0"""
        return max(v, 0)

    # ---- camelCase accessors used by ingestor.py (validated_post.postId etc) ----
    @property
    def postId(self):
        return self.post_id

    @property
    def facebookUrl(self):
        return self.facebook_url

    @property
    def pageName(self):
        return self.page_name

    @property
    def topReactionsCount(self):
        return self.top_reactions_count

    @property
    def feedbackId(self):
        return self.feedback_id

    @property
    def reactionLikeCount(self):
        return self.reaction_like_count

    @property
    def reactionLoveCount(self):
        return self.reaction_love_count

    @property
    def reactionCareCount(self):
        return self.reaction_care_count

    @property
    def reactionSadCount(self):
        return self.reaction_sad_count

    @property
    def reactionHahaCount(self):
        return self.reaction_haha_count

    @property
    def reactionWowCount(self):
        return self.reaction_wow_count

    @property
    def reactionAngryCount(self):
        return self.reaction_angry_count

    @property
    def topLevelUrl(self):
        return self.top_level_url

    @property
    def facebookId(self):
        return self.facebook_id

    @property
    def pageAdLibrary(self):
        return self.page_ad_library

    @property
    def inputUrl(self):
        return self.input_url

    @property
    def isVideo(self):
        return self.is_video

    @property
    def viewsCount(self):
        return self.views_count

    def get_detected_language(self) -> str:
        """
        Simple language detection (placeholder - will be replaced with proper detector)
        """
        # Basic heuristic: check Bengali characters
        if any(char in self.text for char in ['র', 'স', 'ম', 'ক']):
            return 'bn'
        else:
            return 'en'

    def quality_score(self) -> float:
        """
        Calculate data quality score (Layer 1 validation)
        Score based on completeness, timestamp validity, text length, etc.
        """
        score = 0.0
        
        # 1. Timestamp present (20%)
        if self.timestamp and self.time:
            score += 0.2
        
        # 2. Post ID present (10%)
        if self.post_id:
            score += 0.1
        
        # 3. Text completeness (20%)
        text_len = len(self.text)
        if text_len > 100:
            score += 0.2
        elif text_len > 10:
            score += 0.1
        
        # 4. Engagement data present (15%)
        if self.likes >= 0 and self.comments >= 0 and self.shares >= 0:
            score += 0.15
        
        # 5. Media data present (10%)
        if self.media:
            score += 0.1
        
        # 6. User info present (15%)
        if self.user and self.user.get('name'):
            score += 0.15
        
        # 7. URL accessible (10%)
        if self.url.startswith('https://'):
            score += 0.1
        
        return min(score, 1.0)


class ApifyFacebookPostClean(BaseModel):
    """
    Pydantic schema for Apify Facebook post (clean dataset format)
    Clean format strips user info and timestamps
    """
    media: List[Dict[str, Any]]
    url: str
    text: str
    likes: int
    comments: int
    shares: int

    @validator('text')
    def validate_text(cls, v):
        if v is None:
            return ""
        return v.strip()

    def to_full_schema(self, user_info: Dict[str, Any], timestamp: int, post_id: str) -> "ApifyFacebookPost":
        """Convert clean schema to full schema by adding inferred data"""
        return ApifyFacebookPost(
            facebook_url="",  # inferred
            post_id=post_id,
            page_name="",  # inferred
            url=self.url,
            time=datetime.fromtimestamp(timestamp),
            timestamp=timestamp,
            user=user_info,
            collaborators=[],
            text=self.text,
            likes=self.likes,
            comments=self.comments,
            shares=self.shares,
            top_reactions_count=0,
            media=self.media,
            feedback_id=None,
            reaction_like_count=0,
            reaction_love_count=0,
            reaction_care_count=0,
            reaction_sad_count=0,
            reaction_haha_count=0,
            reaction_wow_count=0,
            reaction_angry_count=0,
            top_level_url=None,
            facebook_id=None,
            page_ad_library=None,
            input_url=self.url,
            is_video=False,
            views_count=0
        )


class PostSummary(BaseModel):
    """Summary of validation results"""
    post_id: str
    quality_score: float
    detected_language: str
    text_length: int
    has_media: bool
    timestamp: Optional[int]
    validation_errors: List[str]
    is_valid: bool