"""
Vanta: Claim Extraction Engine (Layer 3)
Extract factual claims from social media posts (global: EN + BN)
"""

import re
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from app.web.models import db
from app.web.models.verification import SocialMediaPost, Claim, ClaimType, LanguageCode
from app.core.ingestion.lang_detect import detect_language

logger = logging.getLogger("Vanta.ClaimExtraction")


class ClaimExtractor:
    """
    Extract factual claims from social media posts
    """
    
    def __init__(self):
        # Claim classification patterns (simple regex for now)
        self.claim_patterns = {
            "bn": [
                r"(\S+)\s+(হয়|করেছে|আছে|হচ্ছে|নিয়েছে|দিয়েছে)\s+(\S+)",  # "X is/has Y"
                r"(\S+)\s+(দ্বারা|হতে|থেকে)\s+(\S+)\s+(হয়েছে|করা হয়েছে)",  # "X was done by Y"
                r"(\S+)\s+(সংখ্যা|পরিমাণ)\s+(\d+)\s+(হয়েছে|আছে)",  # "X number is Y"
                r"(\S+)\s+(তারিখে|সময়ে)\s+(\S+)\s+(ঘটেছে|ঘটে)",  # "X happened at date/time Y"
            ],
            "en": [
                r"(\S+)\s+(is|are|was|were|has|have|had)\s+(\S+)",
                r"(\S+)\s+(announced|said|claimed|stated)\s+that\s+(.+)",
                r"(\S+)\s+(number|amount|count|total)\s+(is|are|was|were)\s+(\d+)",
                r"(\S+)\s+(happened|occurred|took place)\s+(on|at)\s+(\S+)",
            ]
        }
        
        # Opinion/satire indicators
        self.opinion_indicators = {
            "bn": ["মনে হয়", "আমার মতে", "বোধহয়", "সম্ভবত", "হয়তো", "আমি ভাবি"],
            "en": ["I think", "in my opinion", "probably", "maybe", "perhaps", "I believe"]
        }
        
        # Check-worthiness keywords
        self.checkworthy_keywords = {
            "bn": ["সংখ্যা", "পরিমাণ", "আয়", "খরচ", "জনসংখ্যা", "মৃত্যু", "জিডিপি", "মূল্য", "দাম"],
            "en": ["number", "amount", "statistic", "death", "population", "GDP", "price", "cost", "income"]
        }
    
    def split_sentences(self, text: str, language: str = "en") -> List[str]:
        """
        Split text into sentences (simple implementation)
        """
        if not text:
            return []
        
        # Simple sentence splitting
        if language == "bn":
            # Bengali sentence endings
            sentences = re.split(r'[।?!]', text)
        else:
            # English sentence endings
            sentences = re.split(r'[.!?]', text)
        
        # Clean up
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def classify_claim_type(self, sentence: str, language: str) -> Tuple[ClaimType, float]:
        """
        Classify if a sentence contains a factual claim (vs opinion/satire)
        Returns (claim_type, confidence)
        """
        sentence_lower = sentence.lower()
        
        # Check for opinion indicators
        opinion_words = self.opinion_indicators.get(language, [])
        for word in opinion_words:
            if word in sentence_lower:
                return ClaimType.OPINION, 0.8
        
        # Check for numbers (often factual)
        numbers = re.findall(r'\d+', sentence)
        if numbers:
            # Check for checkworthy keywords
            checkworthy_words = self.checkworthy_keywords.get(language, [])
            for word in checkworthy_words:
                if word in sentence_lower:
                    return ClaimType.FACTUAL, 0.7
        
        # Check claim patterns
        patterns = self.claim_patterns.get(language, [])
        for pattern in patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                return ClaimType.FACTUAL, 0.6
        
        # Default to other/opinion
        return ClaimType.OTHER, 0.3
    
    def extract_entities_simple(self, sentence: str, language: str) -> List[Dict[str, Any]]:
        """
        Simple entity extraction (placeholder - replace with proper NER later)
        """
        entities = []
        
        # Extract dates (simple patterns)
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{1,2}/\d{1,2}/\d{4}',  # MM/DD/YYYY
            r'\d{1,2}\s+(জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগস্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর)',
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, sentence, re.IGNORECASE)
            for match in matches:
                entities.append({
                    "text": match,
                    "type": "DATE",
                    "confidence": 0.7
                })
        
        # Extract numbers
        numbers = re.findall(r'\d+[\d,]*\.?\d*', sentence)
        for num in numbers:
            entities.append({
                "text": num,
                "type": "CARDINAL",
                "confidence": 0.9
            })
        
        return entities
    
    def calculate_checkworthiness(self, sentence: str, language: str, claim_type: ClaimType) -> float:
        """
        Calculate check-worthiness score (0.0 - 1.0)
        """
        score = 0.0
        
        # Boost for factual claims
        if claim_type == ClaimType.FACTUAL:
            score += 0.3
        
        # Check for numbers
        numbers = re.findall(r'\d+', sentence)
        if numbers:
            score += 0.2
        
        # Check for checkworthy keywords
        checkworthy_words = self.checkworthy_keywords.get(language, [])
        for word in checkworthy_words:
            if word.lower() in sentence.lower():
                score += 0.2
        
        # Check for length (longer claims might be more checkworthy)
        if len(sentence.split()) > 8:
            score += 0.1
        
        # Check for specific named entities
        if any(entity['type'] == 'DATE' for entity in self.extract_entities_simple(sentence, language)):
            score += 0.2
        
        return min(score, 1.0)
    
    def extract_claims_from_text(self, text: str, language_code: str = "bn") -> List[Dict[str, Any]]:
        """
        Extract claims from text
        """
        if not text:
            return []
        
        # Detect language if not provided
        if not language_code or language_code == "unknown":
            detected_lang, _ = detect_language(text)
            language_code = detected_lang
        
        # Split into sentences
        sentences = self.split_sentences(text, language_code)
        
        claims = []
        
        for i, sentence in enumerate(sentences):
            # Skip very short sentences
            if len(sentence.strip()) < 10:
                continue
            
            # Classify claim type
            claim_type, claim_confidence = self.classify_claim_type(sentence, language_code)
            
            # Calculate check-worthiness
            checkworthiness = self.calculate_checkworthiness(sentence, language_code, claim_type)
            
            # Skip non-factual claims with low check-worthiness
            if claim_type != ClaimType.FACTUAL and checkworthiness < 0.3:
                continue
            
            # Extract entities
            entities = self.extract_entities_simple(sentence, language_code)
            
            # Stable hash for dedup. ROOT CAUSE of duplicate claims on re-run:
            # Python hash() is salted per process (PYTHONHASHSEED), so the
            # dedup lookup never matched after a restart and new claim IDs
            # were minted every run. sha256 of normalized text is stable.
            claim_hash = hashlib.sha256(
                re.sub(r"\s+", " ", sentence.strip().lower()).encode()
            ).hexdigest()
            
            claim_data = {
                "claim_text": sentence.strip(),
                "claim_hash": claim_hash,
                "claim_type": claim_type,
                "claim_type_confidence": claim_confidence,
                "checkworthiness_score": checkworthiness,
                "sentence_index": i,
                "entities": entities,
                "detected_language": language_code,
                "detected_language_confidence": 0.8 if language_code in ["en", "bn"] else 0.5
            }
            
            claims.append(claim_data)

        return claims

    def extract_claims_from_post(self, post: SocialMediaPost) -> List[Claim]:
        """
        Extract claims from a SocialMediaPost and save to database
        """
        # Consolidated: Product B writes `text`, Product A bridge writes `content`.
        # Accept either; prefer `text` when both are set.
        post_text = getattr(post, 'text', None) or getattr(post, 'content', None)
        if not post_text:
            return []

        logger.info(f"Extracting claims from post {post.id}")

        # Get language code
        language_code = post.detected_language.value if post.detected_language and hasattr(post.detected_language, 'value') else str(post.detected_language or 'unknown')

        # Extract claims
        claim_data_list = self.extract_claims_from_text(post_text, language_code)
        
        saved_claims = []
        
        for claim_data in claim_data_list:
            try:
                # Check if claim already exists (by hash)
                existing = db.session.query(Claim).filter_by(
                    claim_hash=claim_data["claim_hash"],
                    post_id=post.id
                ).first()
                
                if existing:
                    logger.debug(f"Claim already exists: {claim_data['claim_hash'][:12]}")
                    saved_claims.append(existing)  # return existing too: pipeline must re-verify/reuse it, not lose it
                    continue
                
                # Create Claim model
                claim = Claim(
                    id=f"claim_{post.id}_{claim_data['claim_hash']}",
                    post_id=post.id,
                    claim_text=claim_data["claim_text"],
                    claim_hash=claim_data["claim_hash"],
                    claim_type=claim_data["claim_type"],
                    claim_type_confidence=claim_data["claim_type_confidence"],
                    check_worthiness_score=claim_data["checkworthiness_score"],
                    sentence_index=claim_data["sentence_index"],
                    entities=claim_data["entities"],
                    detected_language=LanguageCode(claim_data["detected_language"]) if claim_data["detected_language"] in ["en", "bn"] else LanguageCode.UNKNOWN,
                    detected_language_confidence=claim_data["detected_language_confidence"],
                    extraction_model="simple_regex",
                    extracted_at=datetime.utcnow()
                )
                
                db.session.add(claim)
                saved_claims.append(claim)
                
            except Exception as e:
                logger.error(f"Failed to save claim: {e}")
        
        # Update post
        post.processed_for_claims = True
        post.processed_at = datetime.utcnow()
        
        try:
            db.session.commit()
            logger.info(f"Saved {len(saved_claims)} claims for post {post.id}")
        except Exception as e:
            logger.error(f"Failed to commit claims: {e}")
            db.session.rollback()
            return []
        
        return saved_claims
    
    def process_unprocessed_posts(self, limit: int = 100) -> Tuple[int, int]:
        """
        Process unprocessed posts for claim extraction
        Returns (processed_count, claims_extracted_count)
        """
        # Get unprocessed posts
        unprocessed_posts = db.session.query(SocialMediaPost).filter_by(
            processed_for_claims=False
        ).limit(limit).all()
        
        processed_count = 0
        claims_extracted = 0
        
        for post in unprocessed_posts:
            try:
                claims = self.extract_claims_from_post(post)
                processed_count += 1
                claims_extracted += len(claims)
                
                logger.info(f"Processed post {post.id}: extracted {len(claims)} claims")
                
            except Exception as e:
                logger.error(f"Failed to process post {post.id}: {e}")
        
        logger.info(f"Processed {processed_count} posts, extracted {claims_extracted} claims")
        return processed_count, claims_extracted


# Convenience functions
def extract_claims_from_post(post: SocialMediaPost) -> List[Claim]:
    """Convenience function to extract claims from a post"""
    extractor = ClaimExtractor()
    return extractor.extract_claims_from_post(post)


def batch_extract_claims(limit: int = 100) -> Tuple[int, int]:
    """Convenience function for batch processing"""
    extractor = ClaimExtractor()
    return extractor.process_unprocessed_posts(limit)


def create_extractor() -> ClaimExtractor:
    """Factory function to create extractor"""
    return ClaimExtractor()