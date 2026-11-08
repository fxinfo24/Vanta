"""
Vanta: Source Credibility Scorer (Layer 7)
Rate source reliability using Media Bias/Fact Check and other indicators
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("Vanta.Credibility")


class CredibilityTier(Enum):
    TIER_1 = "tier_1"  # Highly credible (0.9-1.0)
    TIER_2 = "tier_2"  # Credible (0.7-0.89)
    TIER_3 = "tier_3"  # Mixed (0.4-0.69)
    TIER_4 = "tier_4"  # Low credibility (0.1-0.39)
    TIER_5 = "tier_5"  # Unreliable (0.0-0.09)


@dataclass
class SourceProfile:
    domain: str
    name: str
    credibility_score: float
    tier: CredibilityTier
    fact_check_rating: Optional[str] = None
    bias_rating: Optional[str] = None
    country: Optional[str] = None
    source_type: str = "news"
    notes: str = ""


class CredibilityScorer:
    """
    Score source credibility using known databases and heuristics
    """
    
    # Known high-credibility sources
    TIER_1_SOURCES = {
        "reuters.com": {"name": "Reuters", "score": 0.95, "bias": "center"},
        "apnews.com": {"name": "Associated Press", "score": 0.95, "bias": "center"},
        "bbc.com": {"name": "BBC", "score": 0.9, "bias": "center-left"},
        "bbc.co.uk": {"name": "BBC", "score": 0.9, "bias": "center-left"},
        "nytimes.com": {"name": "New York Times", "score": 0.85, "bias": "center-left"},
        "washingtonpost.com": {"name": "Washington Post", "score": 0.85, "bias": "center-left"},
        "theguardian.com": {"name": "The Guardian", "score": 0.82, "bias": "center-left"},
        "nature.com": {"name": "Nature", "score": 0.95, "bias": "scientific"},
        "science.org": {"name": "Science", "score": 0.95, "bias": "scientific"},
        "who.int": {"name": "WHO", "score": 0.9, "bias": "institutional"},
        "cdc.gov": {"name": "CDC", "score": 0.9, "bias": "institutional"},
        "gov.bd": {"name": "Bangladesh Government", "score": 0.7, "bias": "government"},
        "prothomalo.com": {"name": "Prothom Alo", "score": 0.8, "bias": "center"},
        "thedailystar.net": {"name": "The Daily Star", "score": 0.78, "bias": "center"},
        "bdnews24.com": {"name": "BDNews24", "score": 0.75, "bias": "center"},
    }
    
    # Known fact-check organizations
    FACT_CHECK_ORGS = {
        "snopes.com": {"name": "Snopes", "score": 0.9},
        "politifact.com": {"name": "PolitiFact", "score": 0.9},
        "factcheck.org": {"name": "FactCheck.org", "score": 0.9},
        "fullfact.org": {"name": "Full Fact", "score": 0.9},
        "boomlive.in": {"name": "BOOM Live", "score": 0.85},
        "altnews.in": {"name": "Alt News", "score": 0.85},
    }
    
    # Known unreliable sources
    UNRELIABLE_SOURCES = {
        "infowars.com": {"name": "Infowars", "score": 0.05},
        "naturalnews.com": {"name": "Natural News", "score": 0.05},
        "breitbart.com": {"name": "Breitbart", "score": 0.25},
    }
    
    def __init__(self):
        self.cache: Dict[str, SourceProfile] = {}
    
    def score_source(self, url_or_domain: str) -> SourceProfile:
        """
        Score a source's credibility
        """
        domain = self._extract_domain(url_or_domain)
        
        # Check cache
        if domain in self.cache:
            return self.cache[domain]
        
        # Check known sources
        profile = self._check_known_sources(domain)
        
        if not profile:
            profile = self._heuristic_score(domain)
        
        self.cache[domain] = profile
        return profile
    
    def _extract_domain(self, url_or_domain: str) -> str:
        """Extract domain from URL or return domain"""
        if "://" in url_or_domain:
            from urllib.parse import urlparse
            parsed = urlparse(url_or_domain)
            domain = parsed.netloc or parsed.path
            return domain.replace("www.", "").lower()
        return url_or_domain.replace("www.", "").lower()
    
    def _check_known_sources(self, domain: str) -> Optional[SourceProfile]:
        """Check against known source databases"""
        
        # Check Tier 1 sources
        if domain in self.TIER_1_SOURCES:
            info = self.TIER_1_SOURCES[domain]
            return SourceProfile(
                domain=domain,
                name=info["name"],
                credibility_score=info["score"],
                tier=CredibilityTier.TIER_1 if info["score"] >= 0.9 else CredibilityTier.TIER_2,
                bias_rating=info.get("bias"),
                source_type="news"
            )
        
        # Check fact-check orgs
        if domain in self.FACT_CHECK_ORGS:
            info = self.FACT_CHECK_ORGS[domain]
            return SourceProfile(
                domain=domain,
                name=info["name"],
                credibility_score=info["score"],
                tier=CredibilityTier.TIER_1,
                fact_check_rating="verified",
                source_type="fact_check"
            )
        
        # Check unreliable sources
        if domain in self.UNRELIABLE_SOURCES:
            info = self.UNRELIABLE_SOURCES[domain]
            return SourceProfile(
                domain=domain,
                name=info["name"],
                credibility_score=info["score"],
                tier=CredibilityTier.TIER_5,
                notes="Known unreliable source"
            )
        
        return None
    
    def _heuristic_score(self, domain: str) -> SourceProfile:
        """
        Apply heuristic scoring for unknown domains
        """
        score = 0.5  # Default neutral score
        
        # Government domains
        if domain.endswith(".gov") or domain.endswith(".gov.bd"):
            score = 0.75
            source_type = "government"
        # Educational domains
        elif domain.endswith(".edu"):
            score = 0.7
            source_type = "academic"
        # Organization domains
        elif domain.endswith(".org"):
            score = 0.6
            source_type = "organization"
        # News indicators
        elif any(ind in domain for ind in ["news", "times", "post", "herald", "tribune"]):
            score = 0.55
            source_type = "news"
        # Blog/personal indicators
        elif any(ind in domain for ind in ["blog", "wordpress", "medium.com", "substack"]):
            score = 0.35
            source_type = "blog"
        else:
            source_type = "unknown"
        
        # Determine tier
        if score >= 0.9:
            tier = CredibilityTier.TIER_1
        elif score >= 0.7:
            tier = CredibilityTier.TIER_2
        elif score >= 0.4:
            tier = CredibilityTier.TIER_3
        elif score >= 0.1:
            tier = CredibilityTier.TIER_4
        else:
            tier = CredibilityTier.TIER_5
        
        return SourceProfile(
            domain=domain,
            name=domain,
            credibility_score=score,
            tier=tier,
            source_type=source_type,
            notes="Heuristic score - unknown source"
        )
    
    def score_evidence_batch(self, evidence_items: List[Dict]) -> List[Dict]:
        """
        Score a batch of evidence items
        """
        scored = []
        
        for item in evidence_items:
            source_url = item.get("source_url", "")
            profile = self.score_source(source_url) if source_url else self._heuristic_score("")
            
            scored.append({
                **item,
                "credibility_score": profile.credibility_score,
                "credibility_tier": profile.tier.value,
                "source_name": profile.name,
                "bias_rating": profile.bias_rating,
                "source_type": profile.source_type
            })
        
        return scored