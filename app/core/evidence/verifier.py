"""
Vanta: Evidence Verifier (Layer 7)
Fact verification engine using multi-source evidence
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.evidence.vector_store import EvidenceVectorStore, EvidenceChunk
from app.core.evidence.credibility import CredibilityScorer, SourceProfile
from app.core.evidence.models import (
    Claim, Evidence, VerificationResult, VerificationStatus,
    SourceType, ExtractionMethod
)

logger = logging.getLogger("Vanta.Verifier")


class EvidenceVerifier:
    """
    Verifies claims against retrieved evidence using multi-source reasoning
    """
    
    def __init__(self, vector_store: EvidenceVectorStore, 
                 credibility_scorer: CredibilityScorer,
                 min_evidence_chunks: int = 3,
                 min_credibility_threshold: float = 0.3):
        self.vector_store = vector_store
        self.credibility_scorer = credibility_scorer
        self.min_evidence_chunks = min_evidence_chunks
        self.min_credibility_threshold = min_credibility_threshold
    
    async def verify_claim(self, claim: Claim) -> VerificationResult:
        """
        Verify a single claim against available evidence
        """
        logger.info(f"Verifying claim: {claim.text[:100]}...")
        
        # Step 1: Retrieve evidence
        evidence_chunks = await self._retrieve_evidence(claim)
        
        if len(evidence_chunks) < self.min_evidence_chunks:
            logger.warning(f"Insufficient evidence: {len(evidence_chunks)} chunks found")
            return self._create_insufficient_evidence_result(claim, evidence_chunks)
        
        # Step 2: Analyze evidence
        analysis = await self._analyze_evidence(claim, evidence_chunks)
        
        # Step 3: Calculate confidence
        confidence = self._calculate_confidence(analysis, evidence_chunks)
        
        # Step 4: Determine verdict
        verdict = self._determine_verdict(analysis, confidence)
        
        # Step 5: Create verification result
        result = VerificationResult(
            claim_id=claim.id,
            status=verdict,
            confidence_score=confidence,
            evidence_used=[chunk.id for chunk in evidence_chunks],
            reasoning=analysis.get("reasoning", ""),
            contradictions=analysis.get("contradictions", []),
            supporting_evidence=analysis.get("supporting", []),
            neutral_evidence=analysis.get("neutral", []),
            metadata={
                "evidence_count": len(evidence_chunks),
                "avg_credibility": sum(chunk.credibility_score for chunk in evidence_chunks) / len(evidence_chunks),
                "source_diversity": len(set(chunk.metadata.get("source") for chunk in evidence_chunks)),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        return result
    
    async def _retrieve_evidence(self, claim: Claim) -> List[EvidenceChunk]:
        """
        Retrieve relevant evidence chunks for a claim
        """
        # Search vector store
        chunks = self.vector_store.search(
            query=claim.text,
            top_k=20,
            filters={"language": claim.language} if claim.language else None
        )
        
        # Also search by entities if available
        if claim.entities:
            for entity in claim.entities[:3]:  # Top 3 entities
                entity_chunks = self.vector_store.search(
                    query=entity.text,
                    top_k=5,
                    filters={"source_type": "official"}
                )
                # Add unique chunks
                existing_ids = {c.id for c in chunks}
                for chunk in entity_chunks:
                    if chunk.id not in existing_ids:
                        chunks.append(chunk)
        
        # Filter by minimum credibility
        chunks = [c for c in chunks if c.credibility_score >= self.min_credibility_threshold]
        
        # Sort by relevance and credibility
        chunks.sort(key=lambda x: x.relevance_score * x.credibility_score, reverse=True)
        
        return chunks[:15]  # Top 15 chunks
    
    async def _analyze_evidence(self, claim: Claim, 
                               chunks: List[EvidenceChunk]) -> Dict[str, Any]:
        """
        Analyze evidence chunks against the claim
        """
        supporting = []
        contradicting = []
        neutral = []
        
        claim_keywords = set(claim.text.lower().split())
        
        for chunk in chunks:
            chunk_keywords = set(chunk.text.lower().split())
            overlap = len(claim_keywords & chunk_keywords) / len(claim_keywords) if claim_keywords else 0
            
            # Simple relevance check
            if overlap > 0.3:
                # Check for contradiction indicators
                if self._has_contradiction_indicators(claim.text, chunk.text):
                    contradicting.append({
                        "chunk_id": chunk.id,
                        "text": chunk.text[:200],
                        "source": chunk.metadata.get("source"),
                        "confidence": chunk.credibility_score
                    })
                else:
                    supporting.append({
                        "chunk_id": chunk.id,
                        "text": chunk.text[:200],
                        "source": chunk.metadata.get("source"),
                        "confidence": chunk.credibility_score
                    })
            elif overlap > 0.1:
                neutral.append({
                    "chunk_id": chunk.id,
                    "text": chunk.text[:200],
                    "source": chunk.metadata.get("source"),
                    "confidence": chunk.credibility_score
                })
        
        # Build reasoning
        reasoning_parts = []
        if supporting:
            reasoning_parts.append(f"Found {len(supporting)} supporting sources")
        if contradicting:
            reasoning_parts.append(f"Found {len(contradicting)} contradicting sources")
        if neutral:
            reasoning_parts.append(f"Found {len(neutral)} neutral/related sources")
        
        return {
            "supporting": supporting,
            "contradictions": contradicting,
            "neutral": neutral,
            "reasoning": ". ".join(reasoning_parts) if reasoning_parts else "No clear evidence alignment"
        }
    
    def _has_contradiction_indicators(self, claim_text: str, evidence_text: str) -> bool:
        """
        Check for contradiction indicators between claim and evidence
        """
        negation_words = {"not", "never", "no", "false", "incorrect", "denied", "refuted", "debunked"}
        
        claim_lower = claim_text.lower()
        evidence_lower = evidence_text.lower()
        
        # Check if evidence contains negation words near claim keywords
        for neg_word in negation_words:
            if neg_word in evidence_lower:
                # Check proximity to claim keywords
                claim_keywords = set(claim_lower.split()) - negation_words
                for keyword in claim_keywords:
                    if keyword in evidence_lower:
                        # Check if negation is within 5 words of keyword
                        neg_pos = evidence_lower.find(neg_word)
                        key_pos = evidence_lower.find(keyword)
                        if abs(neg_pos - key_pos) < 50:  # ~5 words
                            return True
        
        return False
    
    def _calculate_confidence(self, analysis: Dict[str, Any], 
                            chunks: List[EvidenceChunk]) -> float:
        """
        Calculate overall confidence score
        """
        if not chunks:
            return 0.0
        
        # Factor 1: Evidence volume
        total_evidence = len(analysis["supporting"]) + len(analysis["contradictions"]) + len(analysis["neutral"])
        volume_score = min(total_evidence / 5, 1.0)  # Normalize to 5 pieces of evidence
        
        # Factor 2: Source diversity
        unique_sources = len(set(chunk.metadata.get("source", "") for chunk in chunks))
        diversity_score = min(unique_sources / 3, 1.0)  # Normalize to 3 sources
        
        # Factor 3: Average credibility
        avg_credibility = sum(chunk.credibility_score for chunk in chunks) / len(chunks)
        
        # Factor 4: Evidence alignment
        supporting_count = len(analysis["supporting"])
        contradicting_count = len(analysis["contradictions"])
        
        if total_evidence > 0:
            alignment_score = (supporting_count - contradicting_count) / total_evidence
            alignment_score = max(0, alignment_score)  # Floor at 0
        else:
            alignment_score = 0.0
        
        # Weighted combination
        confidence = (
            volume_score * 0.2 +
            diversity_score * 0.2 +
            avg_credibility * 0.3 +
            alignment_score * 0.3
        )
        
        return round(confidence, 3)
    
    def _determine_verdict(self, analysis: Dict[str, Any], confidence: float) -> VerificationStatus:
        """
        Determine verification verdict based on analysis
        """
        supporting_count = len(analysis["supporting"])
        contradicting_count = len(analysis["contradictions"])
        
        if confidence < 0.2:
            return VerificationStatus.INSUFFICIENT_EVIDENCE
        
        if contradicting_count > supporting_count:
            if confidence > 0.7:
                return VerificationStatus.FALSE
            else:
                return VerificationStatus.MISLEADING
        
        if supporting_count > contradicting_count:
            if confidence > 0.7:
                return VerificationStatus.TRUE
            elif confidence > 0.4:
                return VerificationStatus.LIKELY_TRUE
            else:
                return VerificationStatus.UNVERIFIED
        
        if supporting_count == 0 and contradicting_count == 0:
            return VerificationStatus.UNVERIFIED
        
        return VerificationStatus.DISPUTED
    
    def _create_insufficient_evidence_result(self, claim: Claim, 
                                           chunks: List[EvidenceChunk]) -> VerificationResult:
        """Create result when evidence is insufficient"""
        return VerificationResult(
            claim_id=claim.id,
            status=VerificationStatus.INSUFFICIENT_EVIDENCE,
            confidence_score=0.0,
            evidence_used=[chunk.id for chunk in chunks],
            reasoning=f"Only {len(chunks)} evidence chunks found, minimum {self.min_evidence_chunks} required",
            contradictions=[],
            supporting_evidence=[],
            neutral_evidence=[],
            metadata={
                "evidence_count": len(chunks),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


class BatchVerifier:
    """
    Batch verification of multiple claims
    """
    
    def __init__(self, verifier: EvidenceVerifier, batch_size: int = 10):
        self.verifier = verifier
        self.batch_size = batch_size
    
    async def verify_claims(self, claims: List[Claim]) -> List[VerificationResult]:
        """
        Verify multiple claims in batches
        """
        results = []
        
        for i in range(0, len(claims), self.batch_size):
            batch = claims[i:i + self.batch_size]
            logger.info(f"Processing batch {i//self.batch_size + 1}/{(len(claims) + self.batch_size - 1)//self.batch_size}")
            
            batch_tasks = [self.verifier.verify_claim(claim) for claim in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error verifying claim {batch[j].id}: {result}")
                    results.append(VerificationResult(
                        claim_id=batch[j].id,
                        status=VerificationStatus.ERROR,
                        confidence_score=0.0,
                        evidence_used=[],
                        reasoning=f"Error: {str(result)}",
                        contradictions=[],
                        supporting_evidence=[],
                        neutral_evidence=[],
                        metadata={"timestamp": datetime.utcnow().isoformat()}
                    ))
                else:
                    results.append(result)
        
        return results