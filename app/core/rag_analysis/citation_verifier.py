"""
Vanta: Citation Verifier (Layer 6)
Verify that LLM citations are actually grounded in provided evidence
"""

import logging
import re
from typing import List, Dict, Any, Set

logger = logging.getLogger("Vanta.CitationVerifier")


class CitationVerifier:
    """
    Verify LLM citations against source evidence
    """
    
    def __init__(self, min_similarity: float = 0.3):
        self.min_similarity = min_similarity
    
    def verify_citations(self, 
                        reasoning: str,
                        citations: List[Dict],
                        evidence_lines: List[str]) -> Dict[str, Any]:
        """
        Verify all citations in LLM output
        """
        # Extract citation references from reasoning text
        citation_refs = self._extract_citation_references(reasoning)
        
        verified_citations = []
        unverified_citations = []
        
        for citation in citations:
            evidence_id = str(citation.get("evidence_id", ""))
            relevant_text = citation.get("relevant_text", "")
            
            is_verified = self._verify_single_citation(
                evidence_id, relevant_text, evidence_lines
            )
            
            if is_verified:
                verified_citations.append(citation)
            else:
                unverified_citations.append(citation)
        
        total_citations = len(verified_citations) + len(unverified_citations)
        grounding_score = len(verified_citations) / total_citations if total_citations > 0 else 0.0
        
        # Check for hallucination indicators
        hallucination_flags = self._check_hallucination_indicators(
            reasoning, evidence_lines
        )
        
        return {
            "verified_citations": verified_citations,
            "unverified_citations": unverified_citations,
            "total_citations": total_citations,
            "verified_count": len(verified_citations),
            "grounding_score": grounding_score,
            "citation_references": citation_refs,
            "hallucination_flags": hallucination_flags,
            "is_grounded": grounding_score >= 0.7 and len(hallucination_flags) == 0
        }
    
    def _extract_citation_references(self, text: str) -> List[str]:
        """Extract [1], [2] style citations from text"""
        pattern = r'\[(\d+)\]'
        return re.findall(pattern, text)
    
    def _verify_single_citation(self,
                               evidence_id: str,
                               relevant_text: str,
                               evidence_lines: List[str]) -> bool:
        """
        Verify a single citation exists in evidence
        """
        if not evidence_id or not relevant_text:
            return False
        
        # Check if evidence ID exists
        id_exists = any(f"[{evidence_id}]" in line for line in evidence_lines)
        
        if not id_exists:
            return False
        
        # Check if relevant text has similarity to evidence
        relevant_words = set(relevant_text.lower().split())
        
        for line in evidence_lines:
            line_words = set(line.lower().split())
            
            if relevant_words and line_words:
                overlap = len(relevant_words & line_words) / len(relevant_words)
                if overlap >= self.min_similarity:
                    return True
        
        return False
    
    def _check_hallucination_indicators(self,
                                       reasoning: str,
                                       evidence_lines: List[str]) -> List[str]:
        """
        Check for signs of hallucination in reasoning
        """
        flags = []
        
        # Collect all evidence words
        evidence_words: Set[str] = set()
        for line in evidence_lines:
            evidence_words.update(line.lower().split())
        
        # Check reasoning sentences for unsupported claims
        sentences = re.split(r'[.!?]+', reasoning)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 10:
                continue
            
            # Skip sentences that are just citations
            if re.match(r'^\[', sentence):
                continue
            
            sentence_words = set(sentence.lower().split())
            
            # Check for sentences with no evidence overlap
            if sentence_words:
                overlap = len(sentence_words & evidence_words) / len(sentence_words)
                
                if overlap < 0.1 and not self._has_citation(sentence):
                    flags.append(f"Unsupported statement: {sentence[:80]}...")
        
        return flags
    
    def _has_citation(self, text: str) -> bool:
        """Check if text contains a citation reference"""
        return bool(re.search(r'\[\d+\]', text))
    
    def get_verification_summary(self, result: Dict) -> str:
        """Generate human-readable verification summary"""
        parts = []
        
        parts.append(f"Citations: {result['verified_count']}/{result['total_citations']} verified")
        parts.append(f"Grounding score: {result['grounding_score']:.2f}")
        
        if result['hallucination_flags']:
            parts.append(f"Warning: {len(result['hallucination_flags'])} potential hallucinations")
        
        if result['is_grounded']:
            parts.append("Status: GROUNDED")
        else:
            parts.append("Status: NOT GROUNDED")
        
        return " | ".join(parts)