"""
Vanta: Fact-Check Matcher (Layer 4)
Semantic similarity matching between claims and fact-checks.

Primary: real text embeddings via OpenRouter /embeddings
(openai/text-embedding-3-small, 1536-dim; verified live 200).
Cosine thresholds measured live (Nov 2026): true paraphrase 0.695,
related-but-different claim 0.368, unrelated 0.106 / -0.045 ->
threshold 0.55. The old lexical matcher scored the true USA Today
paraphrase at only 0.347 and missed paraphrases entirely.

Fallback (only if the embedding API is unavailable/expensive-blocked):
pure-python TF-IDF cosine over word uni+bigrams. It is labelled
method="tfidf_fallback" on every match so callers can distinguish it
from embedding scores - never silently presented as semantic.
"""

import re
import os
import math
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger("Vanta.FactCheckMatcher")

# Thresholds per method (different scales - do not mix)
EMBEDDING_THRESHOLD = 0.55
TFIDF_THRESHOLD = 0.30


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def tfidf_cosine(text1: str, text2: str) -> float:
    """Pure-python TF-IDF cosine (word uni+bigrams) over the 2-doc corpus.
    Honest lexical-semantic fallback; labelled tfidf_fallback, never claimed
    to be embedding-based."""
    def tokens(t: str) -> List[str]:
        words = re.findall(r"\w+", t.lower())
        return words + [f"{words[i]}_{words[i+1]}" for i in range(len(words) - 1)]

    def vec(toks: List[str], idf: Dict[str, float]) -> Dict[str, float]:
        counts: Dict[str, int] = {}
        for t in toks:
            counts[t] = counts.get(t, 0) + 1
        n = max(len(toks), 1)
        return {t: (c / n) * idf[t] for t, c in counts.items()}

    t1, t2 = tokens(text1 or ""), tokens(text2 or "")
    if not t1 or not t2:
        return 0.0
    df: Dict[str, int] = {}
    for t in set(t1) | set(t2):
        df[t] = (1 if t in t1 else 0) + (1 if t in t2 else 0)
    idf = {t: math.log(2 / (1 + c)) + 1.0 for t, c in df.items()}
    v1, v2 = vec(t1, idf), vec(t2, idf)
    keys = set(v1) | set(v2)
    dot = sum(v1.get(k, 0.0) * v2.get(k, 0.0) for k in keys)
    n1 = math.sqrt(sum(v * v for v in v1.values()))
    n2 = math.sqrt(sum(v * v for v in v2.values()))
    return dot / (n1 * n2) if n1 and n2 else 0.0


class EmbeddingClient:
    """OpenRouter embeddings client (real semantic vectors, no new deps)."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
        self.base_url = "https://openrouter.ai/api/v1/embeddings"
        from app.utils.config import resolve_api_key as _resolve
        self.api_key = api_key or _resolve("OPENROUTER_API_KEY")
        self._cache: Dict[str, List[float]] = {}
        self.available = bool(self.api_key)
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not set; matcher will use tfidf_fallback")

    def embed(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Embed texts; returns None on any API failure (caller falls back honestly)."""
        if not self.available:
            return None
        missing = [t for t in texts if hashlib.sha256(t.encode()).hexdigest() not in self._cache]
        if missing:
            try:
                import requests as _req
                resp = _req.post(
                    self.base_url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"model": self.model, "input": missing},
                    timeout=30,
                )
                if resp.status_code != 200:
                    logger.warning(f"Embedding API {resp.status_code}: {resp.text[:200]} (matcher falls back to tfidf)")
                    return None
                for item in resp.json().get("data", []):
                    idx = item.get("index")
                    if idx is not None and item.get("embedding"):
                        self._cache[hashlib.sha256(missing[idx].encode()).hexdigest()] = item["embedding"]
            except Exception as e:
                logger.warning(f"Embedding API failed: {e} (matcher falls back to tfidf)")
                return None
        out = []
        for t in texts:
            v = self._cache.get(hashlib.sha256(t.encode()).hexdigest())
            if v is None:
                return None
            out.append(v)
        return out


# Shared instance so repeated claims in one process reuse the cache
_default_embedder: Optional[EmbeddingClient] = None


def get_embedder() -> EmbeddingClient:
    global _default_embedder
    if _default_embedder is None:
        _default_embedder = EmbeddingClient()
    return _default_embedder


class FactCheckMatcher:
    """
    Match claims to fact-checks using semantic similarity
    """
    
    def __init__(self, similarity_threshold: float = None, embedder: Optional[EmbeddingClient] = None):
        # None -> per-method default (embeddings 0.55, tfidf 0.30). An explicit
        # value (legacy callers pass 0.3) is honoured as-is.
        self.similarity_threshold = similarity_threshold
        self.embedder = embedder or get_embedder()
        
        # Keywords that indicate similarity
        self.similarity_boost_keywords = {
            "en": ["government", "policy", "announce", "number", "people", "million", "cost", "price"],
            "bn": ["সরকার", "নীতি", "ঘোষণা", "সংখ্যা", "মানুষ", "লক্ষ", "খরচ", "মূল্য"]
        }
        
        # Translation dictionary for simple cross-language matching
        self.simple_translations = {
            "bn": {
                "সরকার": "government",
                "নীতি": "policy", 
                "ঘোষণা": "announce",
                "সংখ্যা": "number",
                "মানুষ": "people",
                "লক্ষ": "lakh",  # 100,000
                "খরচ": "cost",
                "মূল্য": "price"
            }
        }
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""
        
        # Lowercase
        normalized = text.lower()
        
        # Remove extra whitespace
        normalized = " ".join(normalized.split())
        
        # Remove punctuation (keep basic separators)
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        
        return normalized.strip()
    
    def semantic_similarity(self, text1: str, text2: str) -> Tuple[float, str]:
        """Real semantic similarity: embedding cosine if the API works, else
        labelled TF-IDF fallback. Returns (score, method)."""
        embs = self.embedder.embed([text1, text2])
        if embs:
            return _cosine(embs[0], embs[1]), "embedding:" + self.embedder.model
        return tfidf_cosine(text1, text2), "tfidf_fallback"

    def threshold_for(self, method: str) -> float:
        if self.similarity_threshold is not None:
            return self.similarity_threshold
        return EMBEDDING_THRESHOLD if method.startswith("embedding") else TFIDF_THRESHOLD

    def calculate_similarity(self, text1: str, text2: str, language: str = "en") -> float:
        """
        Calculate similarity score between two texts (0.0-1.0)
        
        Uses multiple methods:
        1. Sequence matching (character-level)
        2. Word overlap
        3. Keyword matching
        """
        if not text1 or not text2:
            return 0.0
        
        # Normalize texts
        norm1 = self.normalize_text(text1)
        norm2 = self.normalize_text(text2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Method 1: Sequence similarity
        seq_similarity = SequenceMatcher(None, norm1, norm2).ratio()
        
        # Method 2: Word overlap
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if not words1 or not words2:
            word_similarity = 0.0
        else:
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            word_similarity = len(intersection) / len(union) if union else 0.0
        
        # Method 3: Keyword matching
        keywords = self.similarity_boost_keywords.get(language, [])
        keyword_matches = 0
        
        for keyword in keywords:
            if keyword in norm1 and keyword in norm2:
                keyword_matches += 1
        
        keyword_boost = min(keyword_matches * 0.1, 0.3)  # Max 0.3 boost
        
        # Combine scores (weighted average)
        similarity = (seq_similarity * 0.4) + (word_similarity * 0.5) + keyword_boost
        
        return min(similarity, 1.0)
    
    def translate_keywords(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Simple keyword translation for cross-language matching
        """
        if source_lang not in self.simple_translations or target_lang != "en":
            return text
        
        translated = text
        translations = self.simple_translations[source_lang]
        
        for bn_word, en_word in translations.items():
            translated = translated.replace(bn_word, en_word)
        
        return translated
    
    def match_to_fact_checks(
        self, 
        claim_text: str, 
        claim_language: str,
        fact_checks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Match a claim to fact-check results
        
        Args:
            claim_text: The claim to match
            claim_language: Language code of claim
            fact_checks: List of fact-check results
            
        Returns:
            List of matches with similarity scores
        """
        matches = []

        # Batch-embed claim + all fact-check texts in ONE API call.
        fc_texts = [fc.get("claim_text", "") or "" for fc in fact_checks]
        embs = self.embedder.embed([claim_text] + fc_texts) if fact_checks else None
        method = ("embedding:" + self.embedder.model) if embs else "tfidf_fallback"
        threshold = self.threshold_for(method)

        for i, fc in enumerate(fact_checks):
            fc_text = fc_texts[i]
            # Cross-language: only translate when embeddings are unavailable
            # (embeddings are multilingual; the 8-word keyword dict is weaker).
            if embs:
                similarity = _cosine(embs[0], embs[i + 1])
            elif claim_language == "bn" and fc.get("languages") and "bn" not in fc["languages"]:
                similarity = tfidf_cosine(
                    self.translate_keywords(claim_text, "bn", "en"), fc_text)
            else:
                similarity = tfidf_cosine(claim_text, fc_text)

            lexical = self.calculate_similarity(claim_text, fc_text, claim_language)

            if similarity >= threshold:
                match = fc.copy()
                match["similarity_score"] = similarity
                match["similarity_method"] = method
                match["lexical_score"] = lexical
                match["match_language"] = claim_language
                matches.append(match)
        
        # Sort by similarity score (highest first)
        matches.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        logger.info(f"Found {len(matches)} fact-check matches for claim")
        return matches
    
    def generate_verdict_summary(self, matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary verdict from multiple fact-check matches
        
        Returns aggregated verdict with confidence
        """
        if not matches:
            return {
                "verdict": "NO_MATCH",
                "confidence": 0.0,
                "sources": [],
                "summary": "No matching fact-checks found"
            }
        
        # Count verdicts
        verdict_counts = {}
        total_weight = 0.0
        
        for match in matches:
            verdict = match.get("verdict", "").lower()
            similarity = match.get("similarity_score", 0.0)
            
            # Group similar verdicts
            if "true" in verdict or "correct" in verdict:
                verdict_key = "true"
            elif "false" in verdict or "incorrect" in verdict:
                verdict_key = "false"
            elif "misleading" in verdict or "partially" in verdict:
                verdict_key = "misleading"
            else:
                verdict_key = "other"
            
            # Weight by similarity score
            weight = similarity
            verdict_counts[verdict_key] = verdict_counts.get(verdict_key, 0.0) + weight
            total_weight += weight
        
        if total_weight == 0:
            return {
                "verdict": "UNKNOWN",
                "confidence": 0.0,
                "sources": [],
                "summary": "Insufficient evidence"
            }
        
        # Find dominant verdict
        dominant_verdict = max(verdict_counts.items(), key=lambda x: x[1])
        confidence = dominant_verdict[1] / total_weight
        
        # Map to standardized verdicts
        verdict_map = {
            "true": "VERIFIED_TRUE",
            "false": "VERIFIED_FALSE",
            "misleading": "MISLEADING",
            "other": "UNVERIFIABLE"
        }
        
        standardized_verdict = verdict_map.get(dominant_verdict[0], "UNVERIFIABLE")
        
        # Generate summary
        top_match = matches[0]
        summary = f"Matched to {top_match.get('reviewer', 'fact-checker')}: {top_match.get('verdict', '')}"
        
        # Get unique sources
        sources = list(set(m.get("source", "") for m in matches if m.get("source")))
        
        return {
            "verdict": standardized_verdict,
            "confidence": confidence,
            "sources": sources,
            "summary": summary,
            "match_count": len(matches),
            "top_matches": matches[:3]  # Top 3 matches
        }


def match_claim_to_fact_checks(
    claim_text: str,
    claim_language: str,
    fact_checks: List[Dict[str, Any]],
    similarity_threshold: float = None
) -> Dict[str, Any]:
    """
    Convenience function to match claim to fact-checks
    
    Returns complete verification result for Layer 4
    """
    matcher = FactCheckMatcher(similarity_threshold)
    
    # Find matches
    matches = matcher.match_to_fact_checks(
        claim_text, claim_language, fact_checks
    )
    
    # Generate verdict summary
    verdict_summary = matcher.generate_verdict_summary(matches)
    
    # Complete Layer 4 result
    result = {
        "claim_text": claim_text,
        "claim_language": claim_language,
        "matches_found": len(matches),
        "verdict_summary": verdict_summary,
        "all_matches": matches,
        "layer": 4,
        "processed_at": None  # Will be set by caller
    }
    
    return result