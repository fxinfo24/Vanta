"""
Vanta: ClaimBuster API Integration (Layer 3 Enhancement)
Check-worthy claim detection using ClaimBuster API
"""

import os
import ssl
import json
import logging
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

try:
    import truststore  # OS trust store (see _ssl_context)
    _HAS_TRUSTSTORE = True
except ImportError:
    _HAS_TRUSTSTORE = False

logger = logging.getLogger("Vanta.ClaimBuster")


class ClaimBusterClient:
    """
    ClaimBuster API client for check-worthy claim detection
    
    ClaimBuster identifies factual claims worth fact-checking
    Returns check-worthiness score (0-1)
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("CLAIMBUSTER_API_KEY")
        # Verified live: claimbuster.org/api/v2/* is the working host
        # (idir.uta.edu variants 404; claimbuster.org returns 401 with a
        # bad key, proving the endpoint exists).
        self.base_url = "https://claimbuster.org/api/v2"
        
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
            # Real v2 API (docs + live probe): POST /score/text/ with
            # {"input_text": ...}. (Old code POSTed {"text","language"} to
            # /score - a path that does not exist.)
            # urllib (not requests) so we can verify TLS against the OS
            # trust store: claimbuster.org's Internet2 InCommon CA is not
            # in certifi's Mozilla bundle, so requests fails verification
            # everywhere (verified live). truststore fixes that.
            req = urllib.request.Request(
                f"{self.base_url}/score/text/",
                data=json.dumps({"input_text": text}).encode(),
                headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, context=self._ssl_context(), timeout=15) as resp:
                    status, body = resp.status, resp.read().decode()
            except urllib.error.HTTPError as e:
                status, body = e.code, e.read().decode()
            if status == 200:
                data = json.loads(body)
                score = self._extract_score(data)
                if score is None:
                    return self._unavailable_score(text, language, "unrecognized response shape")
                return {
                    "score": score,
                    "is_checkworthy": score >= 0.5,
                    "confidence": min(score * 2, 1.0),
                    "explanation": self._get_explanation(score),
                    "source": "claimbuster"
                }
            logger.error(f"ClaimBuster API error: {status}")
            return self._unavailable_score(text, language, f"HTTP {status}")
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
    
    @staticmethod
    def _ssl_context() -> ssl.SSLContext:
        if _HAS_TRUSTSTORE:
            return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        return ssl.create_default_context()

    @staticmethod
    def _extract_score(data: Any) -> float:
        """Defensively parse the v2 score response. Exact envelope varies by
        endpoint version; accept the documented shapes and fail loudly
        (return None -> unavailable) rather than inventing a number."""
        if isinstance(data, (int, float)):
            return float(data)
        if isinstance(data, dict):
            for key in ("score", "checkworthiness_score", "claim_score"):
                if isinstance(data.get(key), (int, float)):
                    return float(data[key])
            for key in ("results", "data", "scores"):
                inner = data.get(key)
                if isinstance(inner, list) and inner:
                    return ClaimBusterClient._extract_score(inner[0])
                if isinstance(inner, dict):
                    return ClaimBusterClient._extract_score(inner)
        logger.warning(f"Unrecognized ClaimBuster response shape: {str(data)[:200]}")
        return None

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