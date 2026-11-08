"""
Vanta: Fact-Check Matcher (Layer 4)
Semantic similarity matching between claims and fact-checks
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger("Vanta.FactCheckMatcher")


class FactCheckMatcher:
    """
    Match claims to fact-checks using semantic similarity
    """
    
    def __init__(self, similarity_threshold: float = 0.3):
        self.similarity_threshold = similarity_threshold
        
        # Keywords that indicate similarity
        self.similarity_boost_keywords = {
            "en": ["government", "policy", "announce", "number", "people", "million", "cost", "price"],
            "bn": ["সরকার", "নীতি", "ঘোষণা", "সংখ্যা", "মানুষ", "লক্ষ", "খরচ", "মূল্য"]
        }
        
        # Translation dictionary for simple cross-language matching
        self.simple_translations = {
            "bn": {
                "সরকার": "government",
                "নীতি": "policy", 
                "ঘোষণা": "announce",
                "সংখ্যা": "number",
                "মানুষ": "people",
                "লক্ষ": "lakh",  # 100,000
                "খরচ": "cost",
                "মূল্য": "price"
            }
        }
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""
        
        # Lowercase
        normalized = text.lower()
        
        # Remove extra whitespace
        normalized = " ".join(normalized.split())
        
        # Remove punctuation (keep basic separators)
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        
        return normalized.strip()
    
    def calculate_similarity(self, text1: str, text2: str, language: str = "en") -> float:
        """
        Calculate similarity score between two texts (0.0-1.0)
        
        Uses multiple methods:
        1. Sequence matching (character-level)
        2. Word overlap
        3. Keyword matching
        """
        if not text1 or not text2:
            return 0.0
        
        # Normalize texts
        norm1 = self.normalize_text(text1)
        norm2 = self.normalize_text(text2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Method 1: Sequence similarity
        seq_similarity = SequenceMatcher(None, norm1, norm2).ratio()
        
        # Method 2: Word overlap
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if not words1 or not words2:
            word_similarity = 0.0
        else:
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            word_similarity = len(intersection) / len(union) if union else 0.0
        
        # Method 3: Keyword matching
        keywords = self.similarity_boost_keywords.get(language, [])
        keyword_matches = 0
        
        for keyword in keywords:
            if keyword in norm1 and keyword in norm2:
                keyword_matches += 1
        
        keyword_boost = min(keyword_matches * 0.1, 0.3)  # Max 0.3 boost
        
        # Combine scores (weighted average)
        similarity = (seq_similarity * 0.4) + (word_similarity * 0.5) + keyword_boost
        
        return min(similarity, 1.0)
    
    def translate_keywords(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Simple keyword translation for cross-language matching
        """
        if source_lang not in self.simple_translations or target_lang != "en":
            return text
        
        translated = text
        translations = self.simple_translations[source_lang]
        
        for bn_word, en_word in translations.items():
            translated = translated.replace(bn_word, en_word)
        
        return translated
    
    def match_to_fact_checks(
        self, 
        claim_text: str, 
        claim_language: str,
        fact_checks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Match a claim to fact-check results
        
        Args:
            claim_text: The claim to match
            claim_language: Language code of claim
            fact_checks: List of fact-check results
            
        Returns:
            List of matches with similarity scores
        """
        matches = []
        
        for fc in fact_checks:
            # Check if languages are compatible
            fc_languages = fc.get("languages", [])
            
            # If fact-check has specific languages, check compatibility
            language_compatible = (
                not fc_languages or 
                claim_language in fc_languages or 
                "all" in fc_languages
            )
            
            if not language_compatible:
                # Try cross-language matching
                fc_text_en = fc.get("claim_text", "")
                if claim_language == "bn":
                    # Try translating Bengali claim keywords to English
                    claim_keywords_translated = self.translate_keywords(
                        claim_text, "bn", "en"
                    )
                    similarity = self.calculate_similarity(
                        claim_keywords_translated, fc_text_en, "en"
                    )
                else:
                    # For other language pairs, use direct comparison
                    similarity = self.calculate_similarity(
                        claim_text, fc_text_en, "en"
                    )
            else:
                # Same language matching
                fc_text = fc.get("claim_text", "")
                similarity = self.calculate_similarity(
                    claim_text, fc_text, claim_language
                )
            
            # Add to matches if above threshold
            if similarity >= self.similarity_threshold:
                match = fc.copy()
                match["similarity_score"] = similarity
                match["match_language"] = claim_language
                matches.append(match)
        
        # Sort by similarity score (highest first)
        matches.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        logger.info(f"Found {len(matches)} fact-check matches for claim")
        return matches
    
    def generate_verdict_summary(self, matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary verdict from multiple fact-check matches
        
        Returns aggregated verdict with confidence
        """
        if not matches:
            return {
                "verdict": "NO_MATCH",
                "confidence": 0.0,
                "sources": [],
                "summary": "No matching fact-checks found"
            }
        
        # Count verdicts
        verdict_counts = {}
        total_weight = 0.0
        
        for match in matches:
            verdict = match.get("verdict", "").lower()
            similarity = match.get("similarity_score", 0.0)
            
            # Group similar verdicts
            if "true" in verdict or "correct" in verdict:
                verdict_key = "true"
            elif "false" in verdict or "incorrect" in verdict:
                verdict_key = "false"
            elif "misleading" in verdict or "partially" in verdict:
                verdict_key = "misleading"
            else:
                verdict_key = "other"
            
            # Weight by similarity score
            weight = similarity
            verdict_counts[verdict_key] = verdict_counts.get(verdict_key, 0.0) + weight
            total_weight += weight
        
        if total_weight == 0:
            return {
                "verdict": "UNKNOWN",
                "confidence": 0.0,
                "sources": [],
                "summary": "Insufficient evidence"
            }
        
        # Find dominant verdict
        dominant_verdict = max(verdict_counts.items(), key=lambda x: x[1])
        confidence = dominant_verdict[1] / total_weight
        
        # Map to standardized verdicts
        verdict_map = {
            "true": "VERIFIED_TRUE",
            "false": "VERIFIED_FALSE",
            "misleading": "MISLEADING",
            "other": "UNVERIFIABLE"
        }
        
        standardized_verdict = verdict_map.get(dominant_verdict[0], "UNVERIFIABLE")
        
        # Generate summary
        top_match = matches[0]
        summary = f"Matched to {top_match.get('reviewer', 'fact-checker')}: {top_match.get('verdict', '')}"
        
        # Get unique sources
        sources = list(set(m.get("source", "") for m in matches if m.get("source")))
        
        return {
            "verdict": standardized_verdict,
            "confidence": confidence,
            "sources": sources,
            "summary": summary,
            "match_count": len(matches),
            "top_matches": matches[:3]  # Top 3 matches
        }


def match_claim_to_fact_checks(
    claim_text: str,
    claim_language: str,
    fact_checks: List[Dict[str, Any]],
    similarity_threshold: float = 0.3
) -> Dict[str, Any]:
    """
    Convenience function to match claim to fact-checks
    
    Returns complete verification result for Layer 4
    """
    matcher = FactCheckMatcher(similarity_threshold)
    
    # Find matches
    matches = matcher.match_to_fact_checks(
        claim_text, claim_language, fact_checks
    )
    
    # Generate verdict summary
    verdict_summary = matcher.generate_verdict_summary(matches)
    
    # Complete Layer 4 result
    result = {
        "claim_text": claim_text,
        "claim_language": claim_language,
        "matches_found": len(matches),
        "verdict_summary": verdict_summary,
        "all_matches": matches,
        "layer": 4,
        "processed_at": None  # Will be set by caller
    }
    
    return result