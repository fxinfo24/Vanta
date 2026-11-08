"""
Vanta: Fact-Check Engine (Layer 4 Main)
Orchestrate fact-check API clients and matching
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.web.models import db
from app.web.models.verification import Claim, VerificationResult, VerificationStatus
from app.core.fact_check.clients import create_fact_check_client
from app.core.fact_check.matcher import match_claim_to_fact_checks

logger = logging.getLogger("Vanta.FactCheckEngine")


class FactCheckEngine:
    """
    Main engine for Layer 4 fact-checking
    """
    
    def __init__(self,
                 sources: List[str] = None,
                 similarity_threshold: float = None,
                 cache_results: bool = True):

        # Production default is Google only. The mock client returns fabricated
        # fact-checks and must never run in the live pipeline (kept for tests).
        self.sources = sources or ["google"]
        self.similarity_threshold = similarity_threshold
        self.cache_results = cache_results
        
        # Initialize clients
        self.clients = {}
        for source in self.sources:
            try:
                self.clients[source] = create_fact_check_client(source)
                logger.info(f"Initialized fact-check client: {source}")
            except Exception as e:
                logger.warning(f"Failed to initialize client {source}: {e}")
    
    def fact_check_claim(self, claim: Claim) -> Dict[str, Any]:
        """
        Perform fact-checking on a single claim
        
        Returns Layer 4 verification result
        """
        logger.info(f"Fact-checking claim: {claim.claim_text[:100]}...")
        
        all_fact_checks = []
        
        # Query all configured sources
        for source_name, client in self.clients.items():
            try:
                # Get language from claim
                language = claim.detected_language.value if claim.detected_language else "en"
                
                # Search for fact-checks
                fact_checks = client.search_claim(
                    claim_text=claim.claim_text,
                    language=language,
                    max_age_days=3650  # 10 years: fact-checks for historical claims (e.g. 2020 election) fall outside a 1-year window
                )
                
                logger.info(f"Source {source_name} found {len(fact_checks)} results")
                all_fact_checks.extend(fact_checks)
                
            except Exception as e:
                logger.error(f"Error querying {source_name}: {e}")
        
        # Match claim to fact-checks
        result = match_claim_to_fact_checks(
            claim_text=claim.claim_text,
            claim_language=claim.detected_language.value if claim.detected_language else "en",
            fact_checks=all_fact_checks,
            similarity_threshold=self.similarity_threshold
        )
        
        # Add claim metadata
        result["claim_id"] = claim.id
        result["claim_type"] = claim.claim_type.value
        result["checkworthiness_score"] = claim.check_worthiness_score
        result["processed_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"Fact-check result: {result['verdict_summary']['verdict']} "
                   f"(confidence: {result['verdict_summary']['confidence']:.2f})")
        
        return result
    
    def save_verification_result(self, claim: Claim, result: Dict[str, Any]) -> VerificationResult:
        """
        Save Layer 4 verification result to database
        """
        try:
            # Create or update verification result
            existing = db.session.query(VerificationResult).filter_by(
                claim_id=claim.id
            ).first()
            
            if existing:
                # Update existing
                verification = existing
            else:
                # Create new
                verification = VerificationResult(
                    id=f"verification_{claim.id}",
                    claim_id=claim.id
                )
            
            # Set verification status based on verdict
            verdict_map = {
                "VERIFIED_TRUE": VerificationStatus.VERIFIED_TRUE,
                "VERIFIED_FALSE": VerificationStatus.VERIFIED_FALSE,
                "MISLEADING": VerificationStatus.MISLEADING,
                "UNVERIFIABLE": VerificationStatus.UNVERIFIABLE,
                "NO_MATCH": VerificationStatus.UNVERIFIABLE
            }
            
            verdict_summary = result["verdict_summary"]
            status = verdict_map.get(
                verdict_summary["verdict"],
                VerificationStatus.UNVERIFIABLE
            )
            
            # Update verification result
            verification.verification_status = status
            verification.status = status.value
            verification.confidence_score = verdict_summary["confidence"]
            verification.completed_at = datetime.utcnow()
            
            # Layer 4: Fact-Check results
            verification.fact_check_matches = {
                "matches": result.get("all_matches", []),
                "top_matches": verdict_summary.get("top_matches", [])
            }
            
            verification.fact_check_verdict = verdict_summary["verdict"]
            verification.fact_check_sources = verdict_summary["sources"]
            verification.fact_check_similarity_score = (
                result.get("all_matches", [{}])[0].get("similarity_score", 0.0)
                if result.get("all_matches") else 0.0
            )
            
            # Composite score (Layer 4 only for now)
            verification.composite_verification_score = verdict_summary["confidence"]
            
            # Evidence chain (JSON-safe; both old + new reader paths supported)
            verification.evidence_chain = {
                "layer_4": {
                    "sources_queried": self.sources,
                    "verifications": {"sources_queried": self.sources},
                    "matches_found": result["matches_found"],
                    "verdict_summary": verdict_summary,
                    "processed_at": result["processed_at"] if isinstance(result["processed_at"], str) else str(result["processed_at"])
                }
            }
            
            # Save to database
            if not existing:
                db.session.add(verification)
            
            db.session.commit()
            
            logger.info(f"Saved verification result for claim {claim.id}")
            return verification
            
        except Exception as e:
            logger.error(f"Failed to save verification result: {e}")
            db.session.rollback()
            raise
    
    def process_claim(self, claim: Claim) -> Optional[VerificationResult]:
        """
        Full processing pipeline for a claim
        """
        try:
            # Step 1: Fact-check the claim
            result = self.fact_check_claim(claim)
            
            # Step 2: Save verification result
            verification = self.save_verification_result(claim, result)
            
            return verification
            
        except Exception as e:
            logger.error(f"Failed to process claim {claim.id}: {e}")
            return None
    
    def process_unverified_claims(self, limit: int = 50) -> Dict[str, int]:
        """
        Process claims without verification results
        
        Returns counts of processed claims
        """
        # Find claims without verification results
        from sqlalchemy import not_, exists
        
        unverified_claims = db.session.query(Claim).filter(
            not_(exists().where(VerificationResult.claim_id == Claim.id))
        ).limit(limit).all()
        
        logger.info(f"Found {len(unverified_claims)} unverified claims")
        
        processed = 0
        successful = 0
        failed = 0
        
        for claim in unverified_claims:
            try:
                verification = self.process_claim(claim)
                
                if verification:
                    successful += 1
                    logger.info(f"Successfully verified claim {claim.id}")
                else:
                    failed += 1
                    logger.warning(f"Failed to verify claim {claim.id}")
                
                processed += 1
                
            except Exception as e:
                logger.error(f"Error processing claim {claim.id}: {e}")
                failed += 1
                processed += 1
        
        logger.info(f"Processed {processed} claims: {successful} successful, {failed} failed")
        
        return {
            "processed": processed,
            "successful": successful,
            "failed": failed
        }


def create_fact_check_engine(
    sources: List[str] = None,
    similarity_threshold: float = None
) -> FactCheckEngine:
    """
    Factory function to create fact-check engine
    """
    return FactCheckEngine(
        sources=sources,
        similarity_threshold=similarity_threshold
    )


def verify_claim(claim_id: str) -> Optional[VerificationResult]:
    """
    Convenience function to verify a single claim
    """
    # Get claim from database
    claim = db.session.query(Claim).filter_by(id=claim_id).first()
    
    if not claim:
        logger.error(f"Claim not found: {claim_id}")
        return None
    
    # Create engine and process
    engine = FactCheckEngine()
    return engine.process_claim(claim)


def batch_verify_claims(limit: int = 50) -> Dict[str, int]:
    """
    Convenience function for batch verification
    """
    engine = FactCheckEngine()
    return engine.process_unverified_claims(limit)