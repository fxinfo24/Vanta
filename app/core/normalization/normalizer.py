"""
Vanta: Content Normalization (Layer 2)
Text cleaning, URL expansion, deduplication, language detection
"""
import re
import hashlib
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from dataclasses import dataclass

logger = logging.getLogger("Vanta.Normalization")


@dataclass
class NormalizedContent:
    original_text: str
    normalized_text: str
    language: str
    language_confidence: float
    urls: List[str]
    mentions: List[str]
    hashtags: List[str]
    content_hash: str
    word_count: int
    is_duplicate: bool
    metadata: Dict[str, Any]


class TextCleaner:
    """Clean and normalize social media text"""
    
    def __init__(self):
        self.url_pattern = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')
        self.mention_pattern = re.compile(r'@(\w+)')
        self.hashtag_pattern = re.compile(r'#(\w+)')
        self.whitespace_pattern = re.compile(r'\s+')
        self.emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "]+",
            flags=re.UNICODE
        )
    
    def clean(self, text: str) -> str:
        if not text:
            return ""
        text = self.url_pattern.sub('', text)
        text = self.whitespace_pattern.sub(' ', text)
        return text.strip()
    
    def extract_urls(self, text: str) -> List[str]:
        return self.url_pattern.findall(text) if text else []
    
    def extract_mentions(self, text: str) -> List[str]:
        return self.mention_pattern.findall(text) if text else []
    
    def extract_hashtags(self, text: str) -> List[str]:
        return self.hashtag_pattern.findall(text) if text else []


class LanguageDetector:
    """Detect language using character analysis"""
    
    BN_RANGE = (0x0980, 0x09FF)
    EN_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
    
    def detect(self, text: str) -> tuple:
        if not text:
            return ("unknown", 0.0)
        
        bn_count = sum(1 for c in text if self.BN_RANGE[0] <= ord(c) <= self.BN_RANGE[1])
        en_count = sum(1 for c in text if c in self.EN_CHARS)
        total = max(len(text), 1)
        
        bn_ratio = bn_count / total
        en_ratio = en_count / total
        
        if bn_ratio > 0.15:
            return ("bn", min(0.99, bn_ratio * 3))
        elif en_ratio > 0.3:
            return ("en", min(0.99, en_ratio * 1.5))
        return ("unknown", 0.3)


class Deduplicator:
    """Track and detect duplicate content"""
    
    def __init__(self):
        self.seen_hashes = set()
    
    def compute_hash(self, text: str) -> str:
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def is_duplicate(self, text: str) -> bool:
        h = self.compute_hash(text)
        if h in self.seen_hashes:
            return True
        self.seen_hashes.add(h)
        return False


class ContentNormalizer:
    """Main normalization pipeline"""
    
    def __init__(self):
        self.cleaner = TextCleaner()
        self.lang_detector = LanguageDetector()
        self.deduplicator = Deduplicator()
    
    def normalize(self, text: str, metadata: Dict = None) -> NormalizedContent:
        if not text:
            return NormalizedContent("", "", "unknown", 0.0, [], [], [], "", 0, False, {})
        
        urls = self.cleaner.extract_urls(text)
        mentions = self.cleaner.extract_mentions(text)
        hashtags = self.cleaner.extract_hashtags(text)
        cleaned = self.cleaner.clean(text)
        lang, conf = self.lang_detector.detect(cleaned)
        content_hash = self.deduplicator.compute_hash(cleaned)
        is_dup = self.deduplicator.is_duplicate(cleaned)
        words = len(cleaned.split()) if cleaned else 0
        
        return NormalizedContent(
            original_text=text,
            normalized_text=cleaned,
            language=lang,
            language_confidence=conf,
            urls=urls,
            mentions=mentions,
            hashtags=hashtags,
            content_hash=content_hash,
            word_count=words,
            is_duplicate=is_dup,
            metadata=metadata or {}
        )
    
    def normalize_batch(self, texts: List[str]) -> List[NormalizedContent]:
        return [self.normalize(t) for t in texts]