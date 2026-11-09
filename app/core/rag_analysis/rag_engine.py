"""
Vanta: RAG Engine (Layer 6 Main)
Orchestrate evidence retrieval, LLM analysis, and citation verification
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.web.models import db
from app.web.models.verification import Claim, VerificationResult, VerificationStatus
from .evidence_retriever import EvidenceRetriever
from .llm_analyzer import LLMAnalyzer, LLMProvider, AnalysisResult

logger = logging.getLogger("Vanta.RAGEngine")


class RAGEngine:
    """
    Main RAG engine for Layer 6: AI-Assisted Analysis
    """
    
    def __init__(self,
                 provider: str = "openrouter",
                 model: str = None,
                 temperature: float = 0.1,
                 min_evidence_count: int = 2,
                 min_grounding_score: float = 0.5):
        
        self.provider = LLMProvider(provider)
        # Default to the configured OpenRouter model (Nemotron free by default in
        # openrouter_client). The previous hardcoded anthropic/claude-3.5-sonnet
        # 404s on OpenRouter, so Layer 6 always failed with "LLM call failed: 404".
        from app.utils.config import resolve_openrouter_model as _resolve_model
        self.model = model or _resolve_model()
        self.temperature = temperature
        self.min_evidence_count = min_evidence_count
        self.min_grounding_score = min_grounding_score
        
        # Initialize components
        self.evidence_retriever = EvidenceRetriever(max_evidence_tokens=3000)
        self.llm_analyzer = LLMAnalyzer(
            provider=self.provider,
            model=self.model,
            temperature=self.temperature
        )
    
    def analyze_claim(self, claim: Claim) -> Dict[str, Any]:
        """
        Full RAG analysis pipeline for a single claim
        """
        logger.info(f"RAG analyzing claim: {claim.claim_text[:100]}...")
        
        # Step 1: Retrieve evidence from Layers 4-5
        evidence_result = self.evidence_retriever.retrieve_for_claim(claim)
        
        if not evidence_result["evidence_available"]:
            return {
                "verdict": "UNVERIFIABLE",
                "confidence": 0.0,
                "reasoning": "No evidence available from previous layers",
                "citations": [],
                "evidence_grounded": False,
                "grounding_score": 0.0,
                "evidence_count": 0,
                "layer": 6,
                "processed_at": datetime.utcnow().isoformat()
            }
        
        # Step 2: Format evidence for LLM
        formatted = self.evidence_retriever.format_for_llm(claim, evidence_result)
        
        # Step 3: LLM analysis with grounding
        analysis = self.llm_analyzer.analyze_claim(
            claim_text=claim.claim_text,
            claim_language=claim.detected_language.value if claim.detected_language else "en",
            evidence=formatted
        )
        
        # Step 4: Validate grounding
        if analysis.grounding_score < self.min_grounding_score:
            logger.warning(f"Low grounding score: {analysis.grounding_score:.2f}")
            analysis.verdict = "UNVERIFIABLE"
            analysis.confidence *= analysis.grounding_score
        
        # Step 5: Build result
        result = {
            "verdict": analysis.verdict,
            "confidence": analysis.confidence,
            "reasoning": analysis.reasoning,
            "citations": analysis.citations,
            "evidence_grounded": analysis.evidence_grounded,
            "grounding_score": analysis.grounding_score,
            "evidence_count": evidence_result["evidence_count"],
            "evidence_tokens": evidence_result["total_tokens_estimated"],
            "model_used": analysis.model_used,
            "temperature": analysis.temperature,
            "layer": 6,
            "processed_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"RAG analysis: {result['verdict']} (confidence: {result['confidence']:.2f}, "
                   f"grounding: {result['grounding_score']:.2f})")
        
        return result
    
    def save_rag_result(self, claim: Claim, result: Dict[str, Any]) -> bool:
        """
        Save Layer 6 RAG analysis result
        """
        try:
            verification = db.session.query(VerificationResult).filter_by(
                claim_id=claim.id
            ).first()
            
            if not verification:
                logger.warning(f"No verification result for claim {claim.id}")
                return False
            
            # Update evidence chain with Layer 6
            if not verification.evidence_chain:
                verification.evidence_chain = {}
            
            # Reassign (not in-place mutate): SQLAlchemy JSON columns don't detect
            # in-place dict mutation, so layer_6 would be lost on commit.
            verification.evidence_chain = {
                **verification.evidence_chain,
                "layer_6": {
                    "verdict": result["verdict"],
                    "confidence": result["confidence"],
                    "reasoning": result["reasoning"],
                    "citations": result["citations"],
                    "grounding_score": result["grounding_score"],
                    "evidence_count": result["evidence_count"],
                    "model_used": result.get("model_used", ""),
                    "processed_at": result["processed_at"]
                }
            }
            
            # Update composite score
            layer4 = verification.confidence_score or 0.0
            layer5_conf = 0.0
            layer6_conf = result["confidence"]
            
            if verification.evidence_chain and "layer_5" in verification.evidence_chain:
                layer5_conf = verification.evidence_chain["layer_5"].get("confidence", 0.0)
            
            # Weighted: 40% fact-check, 30% temporal, 30% AI
            verification.composite_verification_score = (
                layer4 * 0.4 + layer5_conf * 0.3 + layer6_conf * 0.3
            )
            
            # Update status based on Layer 6 verdict
            verdict_map = {
                "VERIFIED_TRUE": VerificationStatus.VERIFIED_TRUE,
                "VERIFIED_FALSE": VerificationStatus.VERIFIED_FALSE,
                "MISLEADING": VerificationStatus.MISLEADING,
                "UNVERIFIABLE": VerificationStatus.UNVERIFIABLE,
                "NO_MATCH": VerificationStatus.UNVERIFIABLE,
                "DISPUTED": VerificationStatus.MISLEADING
            }
            
            # Do not let an evidence-less Layer 6 (UNVERIFIABLE) overwrite a concrete
            # Layer 4 verdict (e.g. VERIFIED_FALSE from Google Fact Check). Layer 6's
            # UNVERIFIABLE means "no RAG evidence", not "the fact-check was wrong".
            # Only overwrite when Layer 6 is concrete, or when there is no concrete verdict yet.
            concrete = {"VERIFIED_TRUE", "VERIFIED_FALSE", "MISLEADING", "DISPUTED"}
            existing = verification.verification_status
            existing_is_concrete = existing is not None and existing != VerificationStatus.UNVERIFIABLE
            if result["verdict"] in verdict_map:
                if result["verdict"] in concrete or not existing_is_concrete:
                    verification.verification_status = verdict_map[result["verdict"]]
            verification.status = verification.status_value if hasattr(verification, 'status_value') else None
            
            verification.completed_at = datetime.utcnow()
            
            db.session.commit()
            logger.info(f"Saved RAG result for claim {claim.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save RAG result: {e}")
            db.session.rollback()
            return False
    
    def process_claim(self, claim: Claim) -> Optional[Dict[str, Any]]:
        """
        Full RAG processing pipeline
        """
        try:
            result = self.analyze_claim(claim)
            self.save_rag_result(claim, result)
            return result
        except Exception as e:
            logger.error(f"Failed to process claim {claim.id}: {e}")
            return None
    
    def process_claims(self, limit: int = 50) -> Dict[str, int]:
        """
        Process claims needing Layer 6 analysis
        """
        claims_to_process = []
        
        all_claims = db.session.query(Claim).limit(limit).all()
        
        for claim in all_claims:
            verification = db.session.query(VerificationResult).filter_by(
                claim_id=claim.id
            ).first()
            
            if verification and verification.evidence_chain:
                if "layer_6" not in verification.evidence_chain:
                    claims_to_process.append(claim)
        
        logger.info(f"Found {len(claims_to_process)} claims needing Layer 6 analysis")
        
        processed = 0
        successful = 0
        failed = 0
        
        for claim in claims_to_process:
            result = self.process_claim(claim)
            if result:
                successful += 1
            else:
                failed += 1
            processed += 1
        
        return {
            "processed": processed,
            "successful": successful,
            "failed": failed
        }


def create_rag_engine(**kwargs) -> RAGEngine:
    """Factory function"""
    return RAGEngine(**kwargs)