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
            return self._unavailable_score(text, language)
        
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
            logger.error(f"ClaimBuster API error: {response.status_code}")
            return self._unavailable_score(text, language, f"HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"ClaimBuster API call failed: {e}")
            return self._unavailable_score(text, language, str(e))
    
    def score_claims_batch(self, texts: List[str], language: str = "en") -> List[Dict[str, Any]]:
        """
        Score multiple claims for check-worthiness
        """
        results = []
        for text in texts:
            results.append(self.score_claim(text, language))
        
        return results
    
    def _unavailable_score(self, text: str, language: str, reason: str = "no API key") -> Dict[str, Any]:
        """
        HONEST unavailable result. The old _mock_score returned heuristic
        numbers labelled like real ClaimBuster scores - fabricated data.
        Now: score is None and source is 'unavailable'. Callers MUST NOT
        treat this as a check-worthiness judgement.
        To enable: register at https://claimbuster.org/api/ (free key,
        email verification required - the account owner must do this;
        an agent cannot receive the verification email) and set
        CLAIMBUSTER_API_KEY in .env.
        """
        return {
            "score": None,
            "is_checkworthy": False,
            "confidence": 0.0,
            "explanation": f"ClaimBuster unavailable ({reason}); no score produced",
            "source": "unavailable",
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
            if result.get("source") == "unavailable":
                # Never filter on a fabricated score: pass claims through
                # unchanged so downstream stages still see them.
                claim_data = claims[i].copy()
                claim_data["checkworthiness_score"] = None
                claim_data["checkworthiness_source"] = "unavailable"
                scored_claims.append(claim_data)
                continue
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