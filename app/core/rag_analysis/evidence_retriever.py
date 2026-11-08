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
            evidence_items.extend(fc_evidence)        # Layer 5: Temporal evidence
        if verification.evidence_chain and "layer_5" in verification.evidence_chain:
            temporal_evidence = self._extract_temporal_evidence(
                verification.evidence_chain["layer_5"]
            )
            evidence_items.extend(temporal_evidence)

        # Evidence corpus (live discovery): RAG must not only re-read L4/L5
        # summaries. Query real external sources at claim time and fetch the
        # actual page text of L4/L5 URLs, then rank everything semantically
        # against the claim. Every corpus item carries a real URL + date.
        try:
            corpus_items = self._retrieve_corpus(claim, evidence_items)
            evidence_items.extend(corpus_items)
        except Exception as e:
            logger.warning(f"Evidence corpus retrieval failed (L4/L5 evidence still used): {e}")
            corpus_items = []

        # Calculate token budget
        total_tokens = sum(len(e.get("content", "").split()) for e in evidence_items)
        
        # Trim if needed
        if total_tokens > self.max_evidence_tokens:
            evidence_items = self._rank_and_trim(evidence_items)
        
        return {
            "evidence_available": len(evidence_items) > 0,
            "evidence_count": len(evidence_items),
            "corpus_count": len(corpus_items),
            "corpus_sources": sorted({e.get("source_name", "") for e in corpus_items}),
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
    
    # ---- Evidence corpus (live, real sources only; no vector DB dep) ----

    def _retrieve_corpus(self, claim: Claim, existing: List[Dict]) -> List[Dict]:
        seen_urls = {e.get("url", "") for e in existing if e.get("url")}
        items: List[Dict] = []
        # 1) Web-fetch: real text of pages L4/L5 already found (fact-checks, news)
        for e in existing[:6]:
            url = e.get("url", "")
            if not url or url in seen_urls:
                continue
            text = self._fetch_url_text(url)
            if text:
                seen_urls.add(url)
                items.append({
                    "source_type": "corpus_web_fetch",
                    "source_name": e.get("source_name", "web"),
                    "content": text[:1500],
                    "url": url,
                    "date": e.get("date", ""),
                    "confidence": e.get("confidence", 0.0),
                    "evidence_id": f"fetch_{abs(hash(url)) % (10**8)}",
                })
            if len(items) >= 3:
                break
        # 2) Wikipedia REST summary for the claim phrase (no key, date-agnostic)
        try:
            wiki = self._wikipedia_corpus(claim)
            if wiki:
                items.append(wiki)
        except Exception as e:
            logger.warning(f"Wikipedia corpus failed: {e}")
        # 3) GDELT wide-window global news (no key, date-agnostic-ish)
        try:
            items.extend(self._gdelt_corpus(claim, seen_urls))
        except Exception as e:
            logger.warning(f"GDELT corpus failed: {e}")
        # 4) NewsAPI wide window (needs key; skipped silently if absent)
        try:
            items.extend(self._newsapi_corpus(claim, seen_urls))
        except Exception as e:
            logger.warning(f"NewsAPI corpus failed: {e}")
        # Rank corpus items by semantic similarity to the claim
        if items:
            items = self._rank_corpus(claim, items)
        for it in items:
            seen_urls.add(it.get("url", ""))
        return items

    @staticmethod
    def _fetch_url_text(url: str) -> str:
        import re as _re
        import requests as _req
        try:
            r = _req.get(url, timeout=8, headers={"User-Agent": "Vanta-evidence-corpus/1.0"})
            if r.status_code != 200 or "text/html" not in r.headers.get("Content-Type", "text/html"):
                return ""
            html = r.text
            html = _re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", html)
            text = _re.sub(r"<[^>]+>", " ", html)
            return _re.sub(r"\s+", " ", text).strip()
        except Exception:
            return ""

    def _claim_phrase(self, claim: Claim) -> str:
        stop = {"the","is","are","was","were","has","have","that","this","and",
                "actually","for","with","from","been","will","user","said"}
        import re as _re
        cleaned = _re.sub(r"[^\w\s]", " ", claim.claim_text.lower())
        words = [w for w in cleaned.split() if w not in stop and len(w) > 2]
        return " ".join(words[:5])

    def _wikipedia_corpus(self, claim: Claim) -> Optional[Dict]:
        import requests as _req
        phrase = self._claim_phrase(claim)
        if not phrase:
            return None
        s = _req.get("https://en.wikipedia.org/w/api.php",
                     params={"action": "query", "list": "search", "srsearch": phrase,
                             "format": "json", "srlimit": 1}, timeout=10,
                     headers={"User-Agent": "Vanta-evidence-corpus/1.0"})
        if s.status_code != 200:
            return None
        try:
            hits = s.json().get("query", {}).get("search", [])
        except Exception:
            return None
        if not hits:
            return None
        title = hits[0]["title"]
        summ = _req.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}",
            timeout=10, headers={"User-Agent": "Vanta-evidence-corpus/1.0"})
        data = summ.json() if summ.status_code == 200 else {}
        extract = data.get("extract", "")
        if not extract:
            return None
        return {
            "source_type": "corpus_wikipedia", "source_name": "Wikipedia",
            "content": extract[:1500],
            "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
            "date": data.get("revision_timestamp", "")[:10] if data.get("revision_timestamp") else "",
            "confidence": 0.8,
            "evidence_id": f"wiki_corpus_{abs(hash(title)) % (10**8)}",
        }

    def _claim_date(self, claim: Claim) -> Optional[datetime]:
        from app.web.models.verification import SocialMediaPost
        post = db.session.query(SocialMediaPost).filter_by(id=claim.post_id).first()
        if post and post.timestamp:
            if isinstance(post.timestamp, datetime):
                return post.timestamp
            try:
                return datetime.strptime(str(post.timestamp)[:19], "%Y-%m-%d %H:%M:%S")
            except Exception:
                try:
                    return datetime.strptime(str(post.timestamp)[:10], "%Y-%m-%d")
                except Exception:
                    return None
        return datetime.utcnow()

    def _gdelt_corpus(self, claim: Claim, seen: set) -> List[Dict]:
        from app.core.temporal_verification.clients import GDELTClient
        dt = self._claim_date(claim)
        start = (dt.replace(year=max(dt.year - 10, 2015))).strftime("%Y-%m-%d")
        events = GDELTClient().search_events(
            claim_text=claim.claim_text, start_date=start,
            end_date=dt.strftime("%Y-%m-%d"), country=None)
        out = []
        for ev in events[:5]:
            if ev.get("url") in seen:
                continue
            out.append({
                "source_type": "corpus_gdelt", "source_name": "GDELT",
                "content": ev.get("title", ""), "url": ev.get("url", ""),
                "date": str(ev.get("date", ""))[:10],
                "confidence": ev.get("relevance_score", 0.0),
                "evidence_id": f"gdelt_corpus_{abs(hash(ev.get('url',''))) % (10**8)}",
            })
        return out

    def _newsapi_corpus(self, claim: Claim, seen: set) -> List[Dict]:
        from app.core.temporal_verification.clients import NewsAPIClient
        client = NewsAPIClient()
        if not client.api_key:
            return []
        dt = self._claim_date(claim)
        articles = client.search_articles(
            claim_text=claim.claim_text, claim_date=dt.strftime("%Y-%m-%d"),
            days_before=365, days_after=365)
        out = []
        for a in articles[:5]:
            if a.get("url") in seen:
                continue
            out.append({
                "source_type": "corpus_newsapi", "source_name": a.get("source_name", "NewsAPI"),
                "content": f"{a.get('title','')}. {a.get('description','')}"[:1500],
                "url": a.get("url", ""), "date": str(a.get("published_at",""))[:10],
                "confidence": a.get("relevance_score", 0.0),
                "evidence_id": f"news_corpus_{abs(hash(a.get('url',''))) % (10**8)}",
            })
        return out

    def _rank_corpus(self, claim: Claim, items: List[Dict]) -> List[Dict]:
        """Rank corpus items by semantic similarity to the claim
        (embedding cosine; labelled tfidf fallback if embeddings unavailable)."""
        from app.core.fact_check.matcher import get_embedder, tfidf_cosine, _cosine
        texts = [claim.claim_text] + [it.get("content", "") for it in items]
        embs = get_embedder().embed(texts)
        method = "embedding" if embs else "tfidf_fallback"
        for i, it in enumerate(items):
            score = _cosine(embs[0], embs[i + 1]) if embs else tfidf_cosine(claim.claim_text, it.get("content", ""))
            it["confidence"] = score
            it["relevance_method"] = method
        return sorted(items, key=lambda x: x.get("confidence", 0.0), reverse=True)

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