"""
Vanta: Confidence Scorer (Layer 7 Main)
Aggregate all layer scores into final confidence rating
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

from app.web.models import db
from app.web.models.verification import VerificationResult, VerificationStatus
from .credibility import CredibilityScorer, CredibilityTier

logger = logging.getLogger("Vanta.ConfidenceScorer")


@dataclass
class ConfidenceBreakdown:
    """Detailed confidence breakdown by layer"""
    layer_4_score: float  # Fact-check
    layer_5_score: float  # Temporal
    layer_6_score: float  # RAG analysis
    source_credibility: float  # Source quality
    evidence_volume: float  # Amount of evidence
    evidence_diversity: float  # Diversity of sources
    grounding_score: float  # LLM grounding
    composite_score: float  # Final weighted score
    human_override: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer_4_fact_check": self.layer_4_score,
            "layer_5_temporal": self.layer_5_score,
            "layer_6_rag": self.layer_6_score,
            "source_credibility": self.source_credibility,
            "evidence_volume": self.evidence_volume,
            "evidence_diversity": self.evidence_diversity,
            "grounding_score": self.grounding_score,
            "composite_score": self.composite_score,
            "human_override": self.human_override
        }


class ConfidenceScorer:
    """
    Calculate final confidence scores from all verification layers
    """
    
    # Default weights for each component
    DEFAULT_WEIGHTS = {
        "layer_4": 0.25,       # Fact-check matches
        "layer_5": 0.15,       # Temporal verification
        "layer_6": 0.25,       # RAG analysis
        "credibility": 0.15,   # Source credibility
        "volume": 0.10,        # Evidence volume
        "diversity": 0.10,     # Source diversity
    }
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.credibility_scorer = CredibilityScorer()
    
    def calculate_confidence(self, verification: VerificationResult) -> ConfidenceBreakdown:
        """
        Calculate comprehensive confidence score
        """
        evidence_chain = verification.evidence_chain or {}
        
        # Layer 4: Fact-check score
        layer_4 = self._extract_layer4_score(verification)
        
        # Layer 5: Temporal score
        layer_5 = self._extract_layer5_score(evidence_chain)
        
        # Layer 6: RAG score
        layer_6 = self._extract_layer6_score(evidence_chain)
        
        # Source credibility
        credibility = self._calculate_credibility_score(evidence_chain)
        
        # Evidence volume
        volume = self._calculate_volume_score(evidence_chain)
        
        # Evidence diversity
        diversity = self._calculate_diversity_score(evidence_chain)
        
        # Grounding score (from Layer 6)
        grounding = evidence_chain.get("layer_6", {}).get("grounding_score", 0.0)
        
        # Composite score
        composite = self._calculate_composite(
            layer_4, layer_5, layer_6, credibility, volume, diversity
        )
        
        return ConfidenceBreakdown(
            layer_4_score=layer_4,
            layer_5_score=layer_5,
            layer_6_score=layer_6,
            source_credibility=credibility,
            evidence_volume=volume,
            evidence_diversity=diversity,
            grounding_score=grounding,
            composite_score=composite
        )
    
    def _extract_layer4_score(self, verification: VerificationResult) -> float:
        """Extract Layer 4 fact-check confidence"""
        return verification.confidence_score or 0.0
    
    def _extract_layer5_score(self, evidence_chain: Dict) -> float:
        """Extract Layer 5 temporal confidence"""
        layer5 = evidence_chain.get("layer_5", {})
        return layer5.get("confidence", 0.0)
    
    def _extract_layer6_score(self, evidence_chain: Dict) -> float:
        """Extract Layer 6 RAG confidence"""
        layer6 = evidence_chain.get("layer_6", {})
        return layer6.get("confidence", 0.0)
    
    def _calculate_credibility_score(self, evidence_chain: Dict) -> float:
        """Calculate average source credibility"""
        scores = []
        
        # From fact-check sources
        layer4_matches = evidence_chain.get("layer_4", {}).get("verifications", {})
        if isinstance(layer4_matches, dict):
            for source_name in layer4_matches.get("sources_queried", []):
                profile = self.credibility_scorer.score_source(source_name)
                scores.append(profile.credibility_score)
        
        # From temporal sources
        layer5 = evidence_chain.get("layer_5", {})
        for verif_key in ["news", "events"]:
            verif = layer5.get("verifications", {}).get(verif_key, {})
            if verif.get("articles"):
                for article in verif["articles"][:3]:
                    source = article.get("source_name", "")
                    if source:
                        profile = self.credibility_scorer.score_source(source)
                        scores.append(profile.credibility_score)
        
        return sum(scores) / len(scores) if scores else 0.5
    
    def _calculate_volume_score(self, evidence_chain: Dict) -> float:
        """Calculate evidence volume score"""
        total_items = 0
        
        # Layer 4 matches
        layer4 = evidence_chain.get("layer_4", {})
        total_items += layer4.get("matches_found", 0)
        
        # Layer 5 items
        layer5 = evidence_chain.get("layer_5", {})
        verifications = layer5.get("verifications", {})
        for key in ["news", "events", "urls", "facts"]:
            data = verifications.get(key, {})
            total_items += data.get("total_articles", 0)
            total_items += data.get("total_events", 0)
            total_items += data.get("sources_checked", 0)
        
        # Layer 6 items
        layer6 = evidence_chain.get("layer_6", {})
        total_items += layer6.get("evidence_count", 0)
        
        # Normalize: 10+ items = 1.0
        return min(total_items / 10, 1.0)
    
    def _calculate_diversity_score(self, evidence_chain: Dict) -> float:
        """Calculate source diversity score"""
        sources = set()
        
        # Layer 4 sources
        layer4 = evidence_chain.get("layer_4", {})
        for source in layer4.get("verifications", {}).get("sources_queried", []):
            sources.add(source)
        
        # Layer 5 sources
        layer5 = evidence_chain.get("layer_5", {})
        for source in layer5.get("sources_used", []):
            sources.add(source)
        
        # Normalize: 4+ sources = 1.0
        return min(len(sources) / 4, 1.0)
    
    def _calculate_composite(self, *scores) -> float:
        """Calculate weighted composite score"""
        weight_keys = list(self.weights.keys())
        
        total = 0.0
        for i, score in enumerate(scores):
            if i < len(weight_keys):
                total += score * self.weights[weight_keys[i]]
        
        return min(total, 1.0)
    
    def determine_verdict(self, breakdown: ConfidenceBreakdown) -> str:
        """
        Determine final verdict from confidence breakdown
        """
        score = breakdown.composite_score
        
        if score >= 0.8:
            return "HIGHLY_CONFIDENT"
        elif score >= 0.6:
            return "CONFIDENT"
        elif score >= 0.4:
            return "MODERATE"
        elif score >= 0.2:
            return "LOW_CONFIDENCE"
        else:
            return "INSUFFICIENT"
    
    def needs_human_review(self, breakdown: ConfidenceBreakdown) -> bool:
        """
        Determine if claim needs human review
        """
        # Low confidence
        if breakdown.composite_score < 0.5:
            return True
        
        # Low grounding
        if breakdown.grounding_score < 0.5:
            return True
        
        # Contradictory evidence
        if breakdown.layer_4_score > 0.7 and breakdown.layer_5_score < 0.3:
            return True
        
        # Low source credibility
        if breakdown.source_credibility < 0.4:
            return True
        
        return False
    
    def score_verification(self, verification: VerificationResult) -> Dict[str, Any]:
        """
        Complete scoring pipeline for a verification result
        """
        breakdown = self.calculate_confidence(verification)
        verdict = self.determine_verdict(breakdown)
        needs_review = self.needs_human_review(breakdown)
        
        return {
            "breakdown": breakdown.to_dict(),
            "verdict": verdict,
            "needs_human_review": needs_review,
            "confidence_score": breakdown.composite_score,
            "scored_at": datetime.utcnow().isoformat()
        }