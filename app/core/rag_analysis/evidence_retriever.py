"""
Vanta: Evidence Retriever (Layer 6)
Retrieve verified evidence from Layers 4-5 for RAG analysis
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.web.models import db
from app.web.models.verification import Claim, VerificationResult

logger = logging.getLogger("Vanta.EvidenceRetriever")


class EvidenceRetriever:
    """
    Retrieve and format verified evidence for LLM analysis
    """
    
    def __init__(self, max_evidence_tokens: int = 3000):
        self.max_evidence_tokens = max_evidence_tokens
    
    def retrieve_for_claim(self, claim: Claim) -> Dict[str, Any]:
        """
        Retrieve all available evidence for a claim
        """
        verification = db.session.query(VerificationResult).filter_by(
            claim_id=claim.id
        ).first()
        
        if not verification:
            return {
                "evidence_available": False,
                "reason": "No verification results found",
                "evidence": []
            }
        
        evidence_items = []
        
        # Layer 4: Fact-check evidence
        if verification.fact_check_matches:
            fc_evidence = self._extract_fact_check_evidence(verification)
            evidence_items.extend(fc_evidence)
        
        # Layer 5: Temporal evidence
        if verification.evidence_chain and "layer_5" in verification.evidence_chain:
            temporal_evidence = self._extract_temporal_evidence(
                verification.evidence_chain["layer_5"]
            )
            evidence_items.extend(temporal_evidence)
        
        # Calculate token budget
        total_tokens = sum(len(e.get("content", "").split()) for e in evidence_items)
        
        # Trim if needed
        if total_tokens > self.max_evidence_tokens:
            evidence_items = self._rank_and_trim(evidence_items)
        
        return {
            "evidence_available": len(evidence_items) > 0,
            "evidence_count": len(evidence_items),
            "evidence": evidence_items,
            "total_tokens_estimated": sum(
                len(e.get("content", "").split()) for e in evidence_items
            ),
            "retrieved_at": datetime.utcnow().isoformat()
        }
    
    def _extract_fact_check_evidence(self, verification: VerificationResult) -> List[Dict]:
        """Extract evidence from Layer 4 fact-check results"""
        evidence = []
        
        matches = verification.fact_check_matches or {}
        all_matches = matches.get("matches", [])
        
        for match in all_matches[:5]:  # Top 5 matches
            item = {
                "source_type": "fact_check",
                "source_name": match.get("source", "unknown"),
                "content": match.get("claim_text", ""),
                "verdict": match.get("verdict", ""),
                "url": match.get("url", ""),
                "confidence": match.get("similarity_score", 0.0),
                "evidence_id": f"fc_{hash(match.get('url', ''))}"
            }
            
            if item["content"]:
                evidence.append(item)
        
        # Add verdict summary
        if verification.fact_check_verdict:
            evidence.insert(0, {
                "source_type": "fact_check_summary",
                "source_name": "aggregated",
                "content": f"Fact-check verdict: {verification.fact_check_verdict}",
                "verdict": verification.fact_check_verdict,
                "confidence": verification.fact_check_similarity_score or 0.0,
                "evidence_id": "fc_summary"
            })
        
        return evidence
    
    def _extract_temporal_evidence(self, layer5_data: Dict) -> List[Dict]:
        """Extract evidence from Layer 5 temporal verification"""
        evidence = []
        
        verifications = layer5_data.get("verifications", {})
        
        # News evidence
        news_data = verifications.get("news", {})
        if news_data.get("articles"):
            for article in news_data["articles"][:3]:
                evidence.append({
                    "source_type": "news",
                    "source_name": article.get("source_name", ""),
                    "content": f"{article.get('title', '')}. {article.get('description', '')}",
                    "url": article.get("url", ""),
                    "date": article.get("published_at", ""),
                    "confidence": article.get("relevance_score", 0.0),
                    "evidence_id": f"news_{hash(article.get('url', ''))}"
                })
        
        # GDELT evidence
        events_data = verifications.get("events", {})
        if events_data.get("events"):
            for event in events_data["events"][:3]:
                evidence.append({
                    "source_type": "global_event",
                    "source_name": "GDELT",
                    "content": event.get("title", ""),
                    "url": event.get("url", ""),
                    "date": event.get("date", ""),
                    "confidence": event.get("relevance_score", 0.0),
                    "evidence_id": f"gdelt_{hash(event.get('url', ''))}"
                })
        
        # Wayback evidence
        url_data = verifications.get("urls", {})
        if url_data.get("url_verifications"):
            for uv in url_data["url_verifications"]:
                if uv.get("verified"):
                    snapshot = uv.get("closest_snapshot", {})
                    evidence.append({
                        "source_type": "archived_url",
                        "source_name": "Wayback Machine",
                        "content": f"URL archived: {uv.get('url', '')}",
                        "date": snapshot.get("date", ""),
                        "confidence": 1.0,
                        "evidence_id": f"wb_{hash(uv.get('url', ''))}"
                    })
        
        # Wikipedia evidence
        wiki_data = verifications.get("facts", {})
        if wiki_data.get("topic_verifications"):
            for tv in wiki_data["topic_verifications"]:
                if tv.get("verified") and tv.get("wikipedia_data"):
                    wiki = tv["wikipedia_data"]
                    evidence.append({
                        "source_type": "encyclopedia",
                        "source_name": "Wikipedia",
                        "content": wiki.get("content_preview", ""),
                        "url": f"https://en.wikipedia.org/wiki/{wiki.get('page_title', '').replace(' ', '_')}",
                        "date": wiki.get("revision_date", ""),
                        "confidence": 0.8,
                        "evidence_id": f"wiki_{wiki.get('revision_id', '')}"
                    })
        
        # Temporal plausibility summary
        evidence.insert(0, {
            "source_type": "temporal_summary",
            "source_name": "aggregated",
            "content": f"Temporal plausibility: {layer5_data.get('temporal_plausibility', 'UNKNOWN')}",
            "confidence": layer5_data.get("confidence", 0.0),
            "evidence_id": "temporal_summary"
        })
        
        return evidence
    
    def _rank_and_trim(self, evidence: List[Dict]) -> List[Dict]:
        """Rank evidence by confidence and trim to token budget"""
        # Sort by confidence (highest first)
        ranked = sorted(evidence, key=lambda x: x.get("confidence", 0.0), reverse=True)
        
        trimmed = []
        total_tokens = 0
        
        for item in ranked:
            content_tokens = len(item.get("content", "").split())
            if total_tokens + content_tokens > self.max_evidence_tokens:
                # Include summary items even if over budget
                if item.get("source_type", "").endswith("_summary"):
                    trimmed.append(item)
                break
            trimmed.append(item)
            total_tokens += content_tokens
        
        return trimmed
    
    def format_for_llm(self, claim: Claim, evidence_result: Dict) -> Dict[str, Any]:
        """
        Format evidence for LLM prompt consumption
        """
        evidence_items = evidence_result.get("evidence", [])
        
        # Format as numbered evidence list
        formatted_evidence = []
        for i, item in enumerate(evidence_items, 1):
            source = item.get("source_name", "unknown")
            content = item.get("content", "").strip()
            url = item.get("url", "")
            date = item.get("date", "")
            
            line = f"[{i}] ({source}"
            if date:
                line += f", {date}"
            line += f"): {content}"
            if url:
                line += f" Source: {url}"
            
            formatted_evidence.append(line)
        
        return {
            "claim_text": claim.claim_text,
            "claim_language": claim.detected_language.value if claim.detected_language else "en",
            "evidence_lines": formatted_evidence,
            "evidence_count": len(formatted_evidence),
            "evidence_string": "\n".join(formatted_evidence)
        }