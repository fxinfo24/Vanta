"""
Vanta: ClaimBuster API Integration (Layer 3 Enhancement)
Check-worthy claim detection using ClaimBuster API
"""

import os
import requests
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("Vanta.ClaimBuster")


class ClaimBusterClient:
    """
    ClaimBuster API client for check-worthy claim detection
    
    ClaimBuster identifies factual claims worth fact-checking
    Returns check-worthiness score (0-1)
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("CLAIMBUSTER_API_KEY")
        self.base_url = "https://idir.uta.edu/claimbuster/api/v2"
        
        if not self.api_key:
            logger.warning("ClaimBuster API key not configured")
    
    def score_claim(self, text: str, language: str = "en") -> Dict[str, Any]:
        """
        Score a single claim for check-worthiness
        
        Returns: {
            "score": 0.0-1.0,
            "is_checkworthy": bool,
            "confidence": float,
            "explanation": str
        }
        """
        if not self.api_key:
            return self._mock_score(text, language)
        
        try:
            headers = {
                "x-api-key": self.api_key,
                "Content-Type": "application/json"
            }
            
            payload = {
                "text": text,
                "language": language
            }
            
            response = requests.post(
                f"{self.base_url}/score",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                score = data.get("score", 0.0)
                
                return {
                    "score": score,
                    "is_checkworthy": score >= 0.5,
                    "confidence": min(score * 2, 1.0),
                    "explanation": self._get_explanation(score),
                    "source": "claimbuster"
                }
            else:
                logger.error(f"ClaimBuster API error: {response.status_code}")
                return self._mock_score(text, language)
                
        except Exception as e:
            logger.error(f"ClaimBuster API call failed: {e}")
            return self._mock_score(text, language)
    
    def score_claims_batch(self, texts: List[str], language: str = "en") -> List[Dict[str, Any]]:
        """
        Score multiple claims for check-worthiness
        """
        results = []
        for text in texts:
            results.append(self.score_claim(text, language))
        
        return results
    
    def _mock_score(self, text: str, language: str) -> Dict[str, Any]:
        """
        Mock scoring when API key is not available
        Uses heuristics to estimate check-worthiness
        """
        # Simple heuristics for check-worthiness
        checkworthy_keywords = {
            "en": ["number", "statistic", "percentage", "million", "billion", "announced", "said", "claimed", "government"],
            "bn": ["সংখ্যা", "পরিমাণ", "শতাংশ", "লক্ষ", "কোটি", "ঘোষণা", "বলেছে", "দাবি", "সরকার"]
        }
        
        keywords = checkworthy_keywords.get(language, checkworthy_keywords["en"])
        
        text_lower = text.lower()
        keyword_count = sum(1 for keyword in keywords if keyword in text_lower)
        
        # Simple scoring based on keyword presence
        if keyword_count >= 3:
            score = 0.7
        elif keyword_count >= 1:
            score = 0.4
        else:
            score = 0.1
        
        return {
            "score": score,
            "is_checkworthy": score >= 0.5,
            "confidence": min(score * 1.5, 1.0),
            "explanation": f"Mock score based on {keyword_count} check-worthy keywords",
            "source": "mock"
        }
    
    def _get_explanation(self, score: float) -> str:
        """Generate explanation based on score"""
        if score >= 0.8:
            return "Highly check-worthy factual claim"
        elif score >= 0.6:
            return "Check-worthy factual claim"
        elif score >= 0.4:
            return "Potentially check-worthy claim"
        elif score >= 0.2:
            return "Low check-worthiness"
        else:
            return "Not check-worthy (likely opinion/satire)"
    
    def filter_checkworthy_claims(self, claims: List[Dict[str, Any]], threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        Filter claims by check-worthiness threshold
        
        Claims format: [{"text": "...", "language": "en"}, ...]
        """
        if not claims:
            return []
        
        texts = [claim.get("text", "") for claim in claims]
        languages = [claim.get("language", "en") for claim in claims]
        
        scored_claims = []
        for i, (text, language) in enumerate(zip(texts, languages)):
            result = self.score_claim(text, language)
            
            if result["is_checkworthy"]:
                claim_data = claims[i].copy()
                claim_data["checkworthiness_score"] = result["score"]
                claim_data["checkworthiness_confidence"] = result["confidence"]
                claim_data["checkworthiness_explanation"] = result["explanation"]
                claim_data["checkworthiness_source"] = result["source"]
                scored_claims.append(claim_data)
        
        return scored_claims


def create_claimbuster_client(api_key: str = None) -> ClaimBusterClient:
    """
    Factory function for ClaimBuster client
    """
    return ClaimBusterClient(api_key)