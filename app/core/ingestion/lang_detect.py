"""
Vanta: Language Detection Module
Global language detection for social media text (EN + BN + others)
"""

import os
import logging
from typing import Tuple, Optional
from pathlib import Path

# Try to import fasttext for language detection
try:
    import fasttext
    FASTTEXT_AVAILABLE = True
except ImportError:
    FASTTEXT_AVAILABLE = False

# Fallback to langdetect if fasttext unavailable
try:
    import langdetect
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False


logger = logging.getLogger("Vanta.LangDetect")


class LanguageDetector:
    """
    Language detection engine for global text analysis
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.fasttext_model = None
        self._load_model()
    
    def _load_model(self):
        """Load language detection model"""
        if FASTTEXT_AVAILABLE:
            if self.model_path and os.path.exists(self.model_path):
                try:
                    self.fasttext_model = fasttext.load_model(self.model_path)
                    logger.info(f"Loaded fasttext model from {self.model_path}")
                except Exception as e:
                    logger.warning(f"Failed to load fasttext model: {e}")
                    self.fasttext_model = None
            
            # Try to download model if not available
            if self.fasttext_model is None:
                try:
                    # Try the default fasttext lid.176.bin model
                    model_url = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"
                    logger.info("Fasttext model not found locally, will use fallback")
                except Exception as e:
                    logger.warning(f"Could not initialize fasttext: {e}")
                    self.fasttext_model = None
    
    def detect(self, text: str, min_length: int = 10) -> Tuple[str, float]:
        """
        Detect language of text with confidence score
        Returns (language_code, confidence)
        
        Args:
            text: Text to analyze
            min_length: Minimum text length for detection
        
        Returns:
            Tuple of (language_code, confidence_score)
        """
        if not text or len(text.strip()) < min_length:
            return "unknown", 0.0
        
        cleaned_text = text.strip()
        
        # Try fasttext first (most accurate)
        if FASTTEXT_AVAILABLE and self.fasttext_model:
            try:
                # Fasttext expects text to be clean
                predictions = self.fasttext_model.predict(cleaned_text)
                lang_label = predictions[0][0]  # "__label__en"
                confidence = predictions[1][0]
                
                # Extract language code
                lang_code = lang_label.replace("__label__", "")
                return lang_code, float(confidence)
            except Exception as e:
                logger.warning(f"Fasttext detection failed: {e}")
        
        # Fallback to langdetect
        if LANGDETECT_AVAILABLE:
            try:
                # langdetect can detect multiple languages
                detected_lang = langdetect.detect(cleaned_text)
                # Map langdetect codes to ISO 639-1
                lang_code = detected_lang
                return lang_code, 0.85  # Approximate confidence
            except Exception as e:
                logger.warning(f"Langdetect detection failed: {e}")
        
        # Simple heuristic detection for Bengali vs English
        if self._heuristic_bengali_detection(cleaned_text):
            return "bn", 0.7
        elif self._heuristic_english_detection(cleaned_text):
            return "en", 0.7
        
        return "unknown", 0.0
    
    def _heuristic_bengali_detection(self, text: str) -> bool:
        """
        Simple heuristic for Bengali detection
        Checks for Bengali Unicode characters
        """
        # Bengali Unicode range: U+0980 to U+09FF
        bengali_chars = [
            'র', 'স', 'ম', 'ক', 'ট', 'জ', 'হ', 'ন', 'ব', 'ল', 'প', 'ড', 'ত', 'খ',
            'ি', 'া', 'ো', 'ে', 'ু', 'ী', 'ূ', 'ৈ', 'ো', 'ৌ'
        ]
        
        # Check for any Bengali character
        for char in text:
            if any(b_char in char for b_char in bengali_chars):
                return True
        
        # Check for common Bengali words
        bengali_words = ['এ', 'আ', 'ই', 'উ', 'কি', 'হয়', 'কর', 'দিয়ে', 'নিয়ে']
        for word in bengali_words:
            if word in text:
                return True
        
        return False
    
    def _heuristic_english_detection(self, text: str) -> bool:
        """
        Simple heuristic for English detection
        """
        # Common English words
        english_words = ['the', 'is', 'and', 'of', 'to', 'in', 'that', 'for', 'with', 'on']
        
        # Check for Latin alphabet dominance
        latin_count = 0
        for char in text:
            if ord('a') <= ord(char.lower()) <= ord('z'):
                latin_count += 1
        
        if latin_count > len(text) * 0.5:
            return True
        
        # Check for English words
        lower_text = text.lower()
        for word in english_words:
            if word in lower_text:
                return True
        
        return False
    
    def batch_detect(self, texts: list[str], min_length: int = 10) -> list[Tuple[str, float]]:
        """
        Batch language detection
        """
        results = []
        for text in texts:
            results.append(self.detect(text, min_length))
        return results
    
    def validate_language_code(self, lang_code: str) -> bool:
        """
        Validate language code format (ISO 639-1)
        """
        valid_codes = [
            'en', 'bn', 'es', 'fr', 'de', 'ru', 'ar', 'hi', 'zh', 'ja',
            'ko', 'pt', 'it', 'nl', 'sv', 'da', 'fi', 'no', 'pl', 'tr',
            'th', 'vi', 'id', 'ms', 'tl', 'sw', 'am', 'et', 'so', 'zu'
        ]
        
        # ISO 639-1 codes are 2 letters
        if len(lang_code) != 2:
            return False
        
        return lang_code in valid_codes


def get_language_detector() -> LanguageDetector:
    """
    Factory function to get language detector
    """
    # Check for fasttext model in project data directory
    model_path = None
    data_dir = Path(__file__).parent.parent.parent / "data"
    if data_dir.exists():
        possible_model = data_dir / "lid.176.bin"
        if possible_model.exists():
            model_path = str(possible_model)
    
    return LanguageDetector(model_path)


# Singleton instance
_language_detector = None


def detect_language(text: str, min_length: int = 10) -> Tuple[str, float]:
    """
    Convenience function for single language detection
    """
    global _language_detector
    if _language_detector is None:
        _language_detector = get_language_detector()
    
    return _language_detector.detect(text, min_length)


def batch_detect_languages(texts: list[str], min_length: int = 10) -> list[Tuple[str, float]]:
    """
    Convenience function for batch language detection
    """
    global _language_detector
    if _language_detector is None:
        _language_detector = get_language_detector()
    
    return _language_detector.batch_detect(texts, min_length)