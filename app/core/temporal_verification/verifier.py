"""
Vanta: Temporal & Contextual Verifier (Layer 5)
Main engine for timeline and context verification
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from app.web.models import db
from app.web.models.verification import SocialMediaPost, Claim, VerificationResult
from .clients import create_temporal_client, GDELTClient, WaybackClient, NewsAPIClient, WikipediaClient

logger = logging.getLogger("Vanta.TemporalVerifier")


class TemporalVerifier:
    """
    Main verifier for Layer 5: Temporal & Contextual Verification
    """
    
    def __init__(self, 
                 sources: List[str] = None,
                 min_confidence: float = 0.3):
        
        # GDELT + Wikipedia clients existed but were never in the default list.
        self.sources = sources or ["newsapi", "wayback", "gdelt", "wikipedia"]
        self.min_confidence = min_confidence
        
        # Initialize clients
        self.clients = {}
        for source in self.sources:
            try:
                self.clients[source] = create_temporal_client(source)
                logger.info(f"Initialized temporal client: {source}")
            except Exception as e:
                logger.warning(f"Failed to initialize client {source}: {e}")
    
    def extract_claim_date(self, claim: Claim) -> Optional[str]:
        """
        Extract claim date from post timestamp
        """
        try:
            # Get the post
            post = db.session.query(SocialMediaPost).filter_by(
                id=claim.post_id
            ).first()
            
            if post and post.timestamp:
                # Parse timestamp to YYYY-MM-DD
                if isinstance(post.timestamp, datetime):
                    return post.timestamp.strftime("%Y-%m-%d")
                elif isinstance(post.timestamp, str):
                    # Try to parse common formats
                    for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
                        try:
                            dt = datetime.strptime(post.timestamp[:19], fmt)
                            return dt.strftime("%Y-%m-%d")
                        except:
                            continue
        
        except Exception as e:
            logger.error(f"Failed to extract claim date: {e}")
        
        return None
    
    def extract_urls_from_claim(self, claim: Claim) -> List[str]:
        """
        Extract URLs from claim text
        """
        import re
        
        # Simple URL extraction
        url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*'
        urls = re.findall(url_pattern, claim.claim_text)
        
        # Also check entities for URLs
        for entity in claim.entities or []:
            if entity.get("type") == "URL" and entity.get("text"):
                urls.append(entity["text"])
        
        return list(set(urls))  # Deduplicate
    
    def extract_topics_from_claim(self, claim: Claim) -> List[str]:
        """
        Extract key topics from claim text
        """
        # Single words ("2020", "election") make useless Wikipedia searches.
        # Use one phrase topic: first 4 content words, which Wikipedia search
        # can actually resolve to an article.
        stopwords = {"the", "is", "are", "was", "were", "has", "have", "that", "this",
                     "and", "actually", "for", "with", "from", "were", "been", "will"}
        import re as _re
        cleaned = _re.sub(r"[^\w\s]", " ", claim.claim_text.lower())
        words = [w for w in cleaned.split() if w not in stopwords and len(w) > 2]
        phrase = " ".join(words[:4])
        return [phrase] if phrase else []
    
    def verify_with_newsapi(self, claim: Claim, claim_date: str) -> Dict[str, Any]:
        """
        Verify claim with NewsAPI
        """
        if "newsapi" not in self.clients:
            return {"verified": False, "reason": "NewsAPI client not available"}
        
        client = self.clients["newsapi"]
        
        try:
            articles = client.search_articles(
                claim_text=claim.claim_text,
                claim_date=claim_date,
                days_before=7,
                days_after=7
            )
            
            if not articles:
                return {
                    "verified": False,
                    "reason": "No contemporaneous news articles found",
                    "sources_checked": 1,
                    "confidence": 0.0
                }
            
            # Re-score relevance with embedding cosine (batch: claim + all
            # articles in one call). TF-IDF over long descriptions dilutes to
            # ~0.14 even for on-topic articles; embeddings are the honest
            # semantic measure. Falls back to client TF-IDF if API unavailable.
            relevance_method = "tfidf_cosine"
            try:
                from app.core.fact_check.matcher import get_embedder, _cosine
                texts = [claim.claim_text] + [
                    f"{a.get('title','')} {a.get('description','')}" for a in articles]
                embs = get_embedder().embed(texts)
                if embs:
                    for i, a in enumerate(articles):
                        a["relevance_score"] = _cosine(embs[0], embs[i + 1])
                    relevance_method = "embedding:" + get_embedder().model
            except Exception as e:
                logger.warning(f"Embedding relevance failed, keeping TF-IDF: {e}")

            # Calculate temporal plausibility
            relevance_scores = [a.get("relevance_score", 0.0) for a in articles]
            avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
            
            # Relevance is now TF-IDF cosine (see clients._calculate_news_relevance).
            # Judge by the BEST article, not the average: a single on-topic
            # article proves contemporaneous coverage; averaging over loosely
            # related results (old metric: 0.26) wrongly rejected real coverage.
            top_relevance = max(relevance_scores) if relevance_scores else 0.0
            verified = top_relevance >= 0.35

            return {
                "verified": verified,
                "reason": f"Found {len(articles)} news articles (top relevance: {top_relevance:.2f}, avg: {avg_relevance:.2f})",
                "articles": articles[:5],  # Top 5
                "total_articles": len(articles),
                "avg_relevance": avg_relevance,
                "top_relevance": top_relevance,
                "relevance_method": relevance_method,
                "high_relevance_articles": sum(1 for s in relevance_scores if s >= 0.35),
                "confidence": min(top_relevance, 1.0),
                "sources_checked": len(articles)
            }
            
        except Exception as e:
            logger.error(f"NewsAPI verification error: {e}")
            return {"verified": False, "reason": f"API error: {e}"}
    
    def verify_with_wayback(self, claim: Claim, claim_date: str) -> Dict[str, Any]:
        """
        Verify URLs in claim with Wayback Machine
        """
        if "wayback" not in self.clients:
            return {"verified": False, "reason": "Wayback client not available"}
        
        client = self.clients["wayback"]
        
        urls = self.extract_urls_from_claim(claim)
        
        if not urls:
            return {
                "verified": True,  # No URLs to verify
                "reason": "No URLs in claim to verify",
                "confidence": 1.0
            }
        
        results = []
        all_verified = True
        
        for url in urls[:3]:  # Check first 3 URLs
            try:
                result = client.verify_url_existence(url, claim_date)
                results.append({
                    "url": url,
                    "verified": result["verified"],
                    "closest_snapshot": result.get("closest_snapshot"),
                    "message": result["message"]
                })
                
                if not result["verified"]:
                    all_verified = False
                    
            except Exception as e:
                logger.error(f"Wayback verification error for {url}: {e}")
                results.append({
                    "url": url,
                    "verified": False,
                    "error": str(e)
                })
                all_verified = False
        
        # Calculate confidence based on verification results
        verified_count = sum(1 for r in results if r.get("verified"))
        total_count = len(results)
        
        confidence = verified_count / total_count if total_count > 0 else 1.0
        
        return {
            "verified": all_verified,
            "reason": f"Verified {verified_count}/{total_count} URLs",
            "url_verifications": results,
            "confidence": confidence,
            "sources_checked": total_count
        }
    
    def verify_with_gdelt(self, claim: Claim, claim_date: str) -> Dict[str, Any]:
        """
        Verify claim with GDELT global events
        """
        if "gdelt" not in self.clients:
            return {"verified": False, "reason": "GDELT client not available"}
        
        client = self.clients["gdelt"]
        
        try:
            # Date range: normally +-15d around the post date. BUT if the
            # claim text names a different year (e.g. a 2026 post about the
            # "2020 election"), the contemporaneous window can never match -
            # search the named year instead (honest, documented in reason).
            claim_dt = datetime.strptime(claim_date, "%Y-%m-%d")
            import re as _re
            years = [y for y in _re.findall(r"\b(19|20)\d{2}\b", claim.claim_text)]
            named_year = None
            for y in _re.findall(r"\b((?:19|20)\d{2})\b", claim.claim_text):
                if int(y) != claim_dt.year:
                    named_year = y
                    break
            if named_year:
                start_date, end_date = f"{named_year}-01-01", f"{named_year}-12-31"
            else:
                start_date = (claim_dt - timedelta(days=15)).strftime("%Y-%m-%d")
                end_date = (claim_dt + timedelta(days=15)).strftime("%Y-%m-%d")
            
            events = client.search_events(
                claim_text=claim.claim_text,
                start_date=start_date,
                end_date=end_date,
                country=None  # global search; hardcoding BD hid all non-Bangladeshi events
            )
            
            if not events:
                return {
                    "verified": False,
                    "reason": "No matching events in global database",
                    "confidence": 0.0
                }
            
            # Calculate event relevance
            relevance_scores = [e.get("relevance_score", 0.0) for e in events]
            avg_relevance = sum(relevance_scores) / len(relevance_scores)
            
            # Verify if any event is topically related (TF-IDF cosine now)
            verified = bool(events) and max(relevance_scores) >= 0.30
            
            return {
                "verified": verified,
                "reason": f"Found {len(events)} global events (avg relevance: {avg_relevance:.2f})",
                "events": events[:5],  # Top 5
                "total_events": len(events),
                "avg_relevance": avg_relevance,
                "confidence": min(avg_relevance * 3, 1.0),  # Scale
                "sources_checked": len(events)
            }
            
        except Exception as e:
            logger.error(f"GDELT verification error: {e}")
            return {"verified": False, "reason": f"API error: {e}"}
    
    def verify_with_wikipedia(self, claim: Claim, claim_date: str) -> Dict[str, Any]:
        """
        Verify claim against Wikipedia historical state
        """
        if "wikipedia" not in self.clients:
            return {"verified": False, "reason": "Wikipedia client not available"}
        
        client = self.clients["wikipedia"]
        
        topics = self.extract_topics_from_claim(claim)
        
        if not topics:
            return {
                "verified": True,  # No topics to verify
                "reason": "No specific topics to verify",
                "confidence": 1.0
            }
        
        results = []
        
        for topic in topics[:3]:  # Check first 3 topics
            try:
                fact = client.get_historical_fact(topic, claim_date)
                
                if fact:
                    results.append({
                        "topic": topic,
                        "verified": True,
                        "wikipedia_data": fact,
                        "message": f"Wikipedia had entry for '{topic}' near claim date"
                    })
                else:
                    results.append({
                        "topic": topic,
                        "verified": False,
                        "message": f"No Wikipedia entry for '{topic}' near claim date"
                    })
                    
            except Exception as e:
                logger.error(f"Wikipedia verification error for {topic}: {e}")
                results.append({
                    "topic": topic,
                    "verified": False,
                    "error": str(e)
                })
        
        # Calculate confidence
        verified_count = sum(1 for r in results if r.get("verified"))
        total_count = len(results)
        
        confidence = verified_count / total_count if total_count > 0 else 1.0
        
        return {
            "verified": verified_count > 0,
            "reason": f"Verified {verified_count}/{total_count} topics",
            "topic_verifications": results,
            "confidence": confidence,
            "sources_checked": total_count
        }
    
    def verify_claim_temporally(self, claim: Claim) -> Dict[str, Any]:
        """
        Main verification method for Layer 5
        """
        logger.info(f"Temporally verifying claim: {claim.claim_text[:100]}...")
        
        # Extract claim date
        claim_date = self.extract_claim_date(claim)
        
        if not claim_date:
            return {
                "verified": False,
                "reason": "Could not extract claim date",
                "confidence": 0.0,
                "layer": 5
            }
        
        # Run all available verifications
        verifications = {}
        
        for source in self.sources:
            if source == "newsapi":
                verifications["news"] = self.verify_with_newsapi(claim, claim_date)
            elif source == "wayback":
                verifications["urls"] = self.verify_with_wayback(claim, claim_date)
            elif source == "gdelt":
                verifications["events"] = self.verify_with_gdelt(claim, claim_date)
            elif source == "wikipedia":
                verifications["facts"] = self.verify_with_wikipedia(claim, claim_date)
        
        # Aggregate results
        total_confidence = 0.0
        total_weight = 0.0
        all_verified = True
        
        # Weight different sources
        weights = {
            "news": 0.4,
            "events": 0.3,
            "urls": 0.2,
            "facts": 0.1
        }
        
        for key, result in verifications.items():
            # Include ALL sources: skipping failed checks (old behaviour)
            # inflated confidence to 1.0 from the single no-URLs pass.
            confidence = result.get("confidence", 0.0)
            weight = weights.get(key, 0.1)
            total_confidence += confidence * weight
            total_weight += weight
            if not result.get("verified", True):
                all_verified = False
        
        # Calculate final confidence
        final_confidence = total_confidence / total_weight if total_weight > 0 else 0.0
        
        # Determine temporal plausibility
        if final_confidence >= 0.7:
            plausibility = "HIGHLY_PLAUSIBLE"
        elif final_confidence >= 0.4:
            plausibility = "PLAUSIBLE"
        elif final_confidence >= 0.2:
            plausibility = "WEAK_EVIDENCE"
        else:
            plausibility = "IMPLAUSIBLE"
        
        result = {
            "verified": all_verified,
            "temporal_plausibility": plausibility,
            "confidence": final_confidence,
            "claim_date": claim_date,
            "verifications": verifications,
            "sources_used": self.sources,
            "layer": 5,
            "processed_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Temporal verification: {plausibility} (confidence: {final_confidence:.2f})")
        
        return result
    
    def save_temporal_result(self, claim: Claim, result: Dict[str, Any]) -> bool:
        """
        Save Layer 5 temporal verification result
        """
        try:
            # Get existing verification or create new
            verification = db.session.query(VerificationResult).filter_by(
                claim_id=claim.id
            ).first()
            
            if not verification:
                logger.warning(f"No verification result found for claim {claim.id}")
                return False
            
            # Update with Layer 5 data
            if not verification.evidence_chain:
                verification.evidence_chain = {}
            
            # Reassign (not in-place mutate): SQLAlchemy JSON columns don't detect
            # in-place dict mutation, so layer_5 would be lost on commit.
            verification.evidence_chain = {
                **verification.evidence_chain,
                "layer_5": {
                    "verified": result.get("verified"),
                    "temporal_plausibility": result["temporal_plausibility"],
                    "confidence": result["confidence"],
                    "claim_date": result["claim_date"],
                    "verifications": result["verifications"],
                    "sources_used": result["sources_used"],
                    "processed_at": result["processed_at"]
                }
            }
            
            # Update composite score (weighted with Layer 4)
            layer4_score = verification.confidence_score or 0.0
            layer5_score = result["confidence"]
            
            # Weighted average: 60% fact-check, 40% temporal
            verification.composite_verification_score = (
                layer4_score * 0.6 + layer5_score * 0.4
            )
            
            db.session.commit()
            logger.info(f"Saved temporal verification for claim {claim.id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save temporal result: {e}")
            db.session.rollback()
            return False
    
    def process_claim(self, claim: Claim) -> Optional[Dict[str, Any]]:
        """
        Full temporal verification pipeline
        """
        try:
            # Step 1: Temporal verification
            result = self.verify_claim_temporally(claim)
            
            # Step 2: Save to database
            self.save_temporal_result(claim, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process claim {claim.id}: {e}")
            return None
    
    def process_unverified_claims(self, limit: int = 50) -> Dict[str, int]:
        """
        Process claims without Layer 5 verification
        """
        # Find claims with Layer 4 but no Layer 5
        from sqlalchemy import exists
        
        # Claims with verification result but no layer_5
        claims_to_process = []
        
        all_claims = db.session.query(Claim).limit(limit).all()
        
        for claim in all_claims:
            verification = db.session.query(VerificationResult).filter_by(
                claim_id=claim.id
            ).first()
            
            if verification and verification.evidence_chain:
                if "layer_5" not in verification.evidence_chain:
                    claims_to_process.append(claim)
        
        logger.info(f"Found {len(claims_to_process)} claims needing Layer 5 verification")
        
        processed = 0
        successful = 0
        failed = 0
        
        for claim in claims_to_process:
            try:
                result = self.process_claim(claim)
                
                if result:
                    successful += 1
                else:
                    failed += 1
                
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


def verify_claim_temporally(claim: Claim) -> Optional[Dict[str, Any]]:
    """
    Convenience function for temporal verification
    """
    verifier = TemporalVerifier()
    return verifier.process_claim(claim)


def create_temporal_verifier(sources: List[str] = None) -> TemporalVerifier:
    """
    Factory function
    """
    return TemporalVerifier(sources=sources)