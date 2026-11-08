"""
Vanta: Fact-Check API Clients (Layer 4)
API clients for external fact-check databases
"""

import os
import json
import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("Vanta.FactCheck")


class FactCheckClient:
    """Base class for fact-check API clients"""
    
    def __init__(self, api_key: Optional[str] = None, rate_limit: int = 10):
        self.api_key = api_key
        self.rate_limit = rate_limit  # requests per minute
        self.last_request_time = None
        self.request_count = 0
    
    def _rate_limit_check(self):
        """Simple rate limiting"""
        # TODO: Implement proper rate limiting
        pass
    
    def search_claim(self, claim_text: str, language: str = "en", **kwargs) -> List[Dict[str, Any]]:
        """Search for fact-checks matching a claim"""
        raise NotImplementedError
    
    def normalize_results(self, raw_results: List[Dict]) -> List[Dict[str, Any]]:
        """Normalize fact-check results to common format"""
        normalized = []
        
        for result in raw_results:
            normalized_result = {
                "source": self.get_source_name(),
                "external_id": result.get("id", ""),
                "claim_text": result.get("text", ""),
                "verdict": result.get("verdict", ""),
                "verdict_date": result.get("date", ""),
                "explanation": result.get("explanation", ""),
                "reviewer": result.get("reviewer", ""),
                "rating": result.get("rating", ""),
                "url": result.get("url", ""),
                "languages": result.get("languages", []),
                "categories": result.get("categories", []),
                "raw_data": result
            }
            normalized.append(normalized_result)
        
        return normalized
    
    def get_source_name(self) -> str:
        """Get source name for this client"""
        raise NotImplementedError


class GoogleFactCheckClient(FactCheckClient):
    """
    Google Fact Check Tools API client
    https://developers.google.com/fact-check/tools/api/reference/rest
    """
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.base_url = "https://factchecktools.googleapis.com/v1alpha1"
        
        # Load API key from environment if not provided
        if not api_key:
            self.api_key = os.getenv("GOOGLE_FACT_CHECK_API_KEY")
        
        if not self.api_key:
            logger.warning("Google Fact Check API key not configured")
    
    def get_source_name(self) -> str:
        return "google_fact_check"
    
    def search_claim(self, claim_text: str, language: str = "en", max_age_days: int = 365, **kwargs) -> List[Dict[str, Any]]:
        """
        Search Google Fact Check database
        
        Args:
            claim_text: Claim to fact-check
            language: Language code (e.g., "en", "bn")
            max_age_days: Maximum age of fact-checks in days
            
        Returns:
            List of fact-check results
        """
        if not self.api_key or self.api_key == "your_google_fact_check_api_key_here":
            logger.warning("Google Fact Check API key not configured, returning empty results")
            return []
        
        try:
            self._rate_limit_check()
            
            # Prepare request
            endpoint = f"{self.base_url}/claims:search"
            params = {
                "key": self.api_key,
                "query": claim_text[:500],  # Google has length limits
                "languageCode": language,
                "maxAgeDays": max_age_days
            }
            
            # Add optional parameters
            if "publisher" in kwargs:
                params["publisher"] = kwargs["publisher"]
            if "review_date_after" in kwargs:
                params["reviewDate.after"] = kwargs["review_date_after"]
            
            # Make request
            response = requests.get(endpoint, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Google Fact Check API error: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            
            # Parse claims.
            # Real API shape (verified live): 
            #   {"text": claim text, "claimant": ..., "claimReview": [{publisher, url, title, reviewDate, textualRating}]}
            # Older code assumed a nested {"claim": {...}} wrapper that the API never returns,
            # so claim text was always "" and the matcher dropped every Google result (NO_MATCH).
            raw_results = []
            for item in data.get("claims", []):
                claim_text = item.get("text", "") or item.get("claim", {}).get("text", "")
                reviews = item.get("claimReview") or [{}]
                for claim_review in reviews:
                    result = {
                        "id": item.get("name", ""),
                        "text": claim_text,
                        "claimant": item.get("claimant", ""),
                        "claim_date": item.get("claimDate", ""),
                        "verdict": claim_review.get("textualRating", ""),
                        "verdict_date": claim_review.get("reviewDate", ""),
                        "explanation": claim_review.get("title", ""),  # review title is the closest summary Google gives
                        "reviewer": claim_review.get("publisher", {}).get("name", ""),
                        "url": claim_review.get("url", ""),
                        "languages": [language],
                        "categories": [],
                        "similarity_score": 0.0  # Will be calculated by matcher
                    }
                    raw_results.append(result)
            
            logger.info(f"Google Fact Check found {len(raw_results)} results for: {claim_text[:50]}...")
            return self.normalize_results(raw_results)
            
        except Exception as e:
            logger.error(f"Google Fact Check API error: {e}")
            return []


class FullFactClient(FactCheckClient):
    """
    Full Fact API client (UK fact-checking organization)
    https://fullfact.org/
    """
    
    def __init__(self):
        super().__init__(api_key=None)  # No API key needed
        self.base_url = "https://fullfact.org"
        self.api_endpoint = "https://fullfact.org/api"  # Note: May require registration
    
    def get_source_name(self) -> str:
        return "full_fact"
    
    def search_claim(self, claim_text: str, language: str = "en", **kwargs) -> List[Dict[str, Any]]:
        """
        Search Full Fact database (UK-focused)
        
        Note: Full Fact API may require registration/API key
        """
        # For now, return mock data or empty
        # TODO: Implement actual Full Fact API when available
        
        logger.info(f"Full Fact would search for: {claim_text[:50]}... (API not implemented)")
        
        # Mock response for development
        mock_results = [
            {
                "id": "full_fact_mock_001",
                "text": "Example claim about UK politics",
                "verdict": "Correct",
                "verdict_date": "2024-01-15",
                "explanation": "This is a mock fact-check for development.",
                "reviewer": "Full Fact",
                "url": "https://fullfact.org/example",
                "languages": ["en"],
                "categories": ["politics"]
            }
        ]
        
        return self.normalize_results(mock_results)


class MockFactCheckClient(FactCheckClient):
    """
    Mock fact-check client for development/testing
    """
    
    def __init__(self):
        super().__init__(api_key=None)
        self.mock_database = self._load_mock_data()
    
    def get_source_name(self) -> str:
        return "mock_fact_check"
    
    def _load_mock_data(self) -> List[Dict[str, Any]]:
        """Load mock fact-check data for development"""
        return [
            {
                "id": "mock_001",
                "text": "The government announced new policies.",
                "verdict": "True",
                "verdict_date": "2024-01-10",
                "explanation": "The government did announce new policies on January 10, 2024.",
                "reviewer": "Mock Fact-Checker",
                "url": "https://example.com/fact-check/001",
                "languages": ["en"],
                "categories": ["politics"]
            },
            {
                "id": "mock_002", 
                "text": "10 million people will benefit from the new policy.",
                "verdict": "Partially True",
                "verdict_date": "2024-01-12",
                "explanation": "Government estimates suggest 8-12 million people could benefit.",
                "reviewer": "Mock Fact-Checker",
                "url": "https://example.com/fact-check/002",
                "languages": ["en"],
                "categories": ["politics", "economics"]
            },
            {
                "id": "mock_003",
                "text": "গতকাল সরকার নতুন নীতি ঘোষণা করেছে।",
                "verdict": "True",
                "verdict_date": "2024-01-15",
                "explanation": "গতকাল সরকার সত্যিই নতুন নীতি ঘোষণা করেছে।",
                "reviewer": "Mock Bengali Fact-Checker",
                "url": "https://example.com/fact-check/003",
                "languages": ["bn"],
                "categories": ["politics"]
            }
        ]
    
    def search_claim(self, claim_text: str, language: str = "en", **kwargs) -> List[Dict[str, Any]]:
        """
        Mock search - returns all results for development
        """
        logger.info(f"Mock fact-check search for: {claim_text[:50]}...")
        
        # Filter by language if specified
        filtered = [
            item for item in self.mock_database 
            if language in item["languages"] or language == "all"
        ]
        
        return self.normalize_results(filtered)


def create_fact_check_client(source: str = "google", **kwargs) -> FactCheckClient:
    """
    Factory function to create fact-check clients
    
    Args:
        source: "google", "fullfact", "mock", or "all"
        **kwargs: Client-specific configuration
    """
    if source == "google":
        return GoogleFactCheckClient(**kwargs)
    elif source == "fullfact":
        return FullFactClient(**kwargs)
    elif source == "mock":
        return MockFactCheckClient(**kwargs)
    else:
        raise ValueError(f"Unknown fact-check source: {source}")