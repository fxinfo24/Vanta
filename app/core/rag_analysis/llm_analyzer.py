"""
Vanta: LLM Analyzer (Layer 6)
Grounded LLM analysis with evidence constraints
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("Vanta.LLMAnalyzer")


class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"


@dataclass
class AnalysisResult:
    verdict: str
    confidence: float
    reasoning: str
    citations: List[Dict[str, Any]]
    evidence_grounded: bool
    grounding_score: float
    raw_response: str
    model_used: str
    temperature: float


class LLMAnalyzer:
    """
    LLM-based claim analyzer with evidence grounding constraints
    """
    
    def __init__(self, 
                 provider: LLMProvider = LLMProvider.OPENROUTER,
                 model: str = "anthropic/claude-3.5-sonnet",
                 temperature: float = 0.1,
                 max_tokens: int = 1000,
                 api_key: Optional[str] = None):
        
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key = api_key or self._get_api_key()
        
        # System prompt for grounded analysis
        self.system_prompt = """You are a fact-checking analyst. Your task is to analyze claims based ONLY on the provided evidence.

STRICT RULES:
1. ONLY use information from the provided evidence sources
2. You MUST cite specific evidence numbers [1], [2], etc. for every statement
3. If evidence is insufficient, state "INSUFFICIENT EVIDENCE" instead of speculating
4. Do NOT add information not present in the evidence
5. Do NOT use prior knowledge - only the provided evidence
6. Rate your confidence based on evidence quality and quantity

VERDICT OPTIONS:
- VERIFIED_TRUE: Clear evidence supports the claim
- VERIFIED_FALSE: Clear evidence contradicts the claim  
- MISLEADING: Claim has some truth but is misleading
- UNVERIFIABLE: Insufficient evidence to verify
- DISPUTED: Evidence is contradictory

RESPONSE FORMAT (JSON):
{
    "verdict": "VERIFIED_TRUE|VERIFIED_FALSE|MISLEADING|UNVERIFIABLE|DISPUTED",
    "confidence": 0.0-1.0,
    "reasoning": "Detailed reasoning with citations [1][2]...",
    "citations": [{"evidence_id": "1", "relevant_text": "quote from evidence"}],
    "evidence_grounded": true/false,
    "grounding_score": 0.0-1.0
}"""
    
    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment"""
        if self.provider == LLMProvider.OPENAI:
            return os.getenv("OPENAI_API_KEY")
        elif self.provider == LLMProvider.ANTHROPIC:
            return os.getenv("ANTHROPIC_API_KEY")
        elif self.provider == LLMProvider.OPENROUTER:
            return os.getenv("OPENROUTER_API_KEY")
        return None
    
    def analyze_claim(self, 
                     claim_text: str,
                     claim_language: str,
                     evidence: Dict[str, Any]) -> AnalysisResult:
        """
        Analyze a claim against provided evidence
        
        Uses strict grounding to prevent hallucination
        """
        logger.info(f"Analyzing claim: {claim_text[:80]}...")
        
        # Format evidence for LLM
        formatted = self._format_evidence(claim_text, claim_language, evidence)
        
        # Generate LLM prompt
        user_prompt = self._build_prompt(formatted)
        
        # Call LLM
        raw_response = self._call_llm(user_prompt)
        
        # Parse response
        result = self._parse_response(raw_response)
        
        # Verify grounding
        grounding_score = self._verify_grounding(result, evidence)
        result.grounding_score = grounding_score
        result.evidence_grounded = grounding_score >= 0.7
        result.model_used = self.model
        result.temperature = self.temperature
        
        logger.info(f"Analysis complete: {result.verdict} (confidence: {result.confidence:.2f})")
        
        return result
    
    def _format_evidence(self, claim_text: str, language: str, evidence: Dict) -> str:
        """Format evidence for LLM consumption"""
        lines = [
            f"CLAIM TO VERIFY: {claim_text}",
            f"CLAIM LANGUAGE: {language}",
            "",
            "EVIDENCE SOURCES:",
            ""
        ]
        
        evidence_items = evidence.get("evidence_lines", [])
        for i, item in enumerate(evidence_items, 1):
            lines.append(f"[{i}] {item}")
        
        if not evidence_items:
            lines.append("NO EVIDENCE AVAILABLE")
        
        return "\n".join(lines)
    
    def _build_prompt(self, formatted_evidence: str) -> str:
        """Build the user prompt"""
        return f"""Analyze the following claim based ONLY on the provided evidence.

{formatted_evidence}

Remember:
- ONLY use the provided evidence
- Cite evidence numbers [1][2] for every statement
- If evidence is insufficient, say so
- Return your analysis as JSON

Analyze the claim now:"""
    
    def _call_llm(self, prompt: str) -> str:
        """Call the LLM API"""
        try:
            if self.provider == LLMProvider.OPENROUTER:
                return self._call_openrouter(prompt)
            elif self.provider == LLMProvider.OPENAI:
                return self._call_openai(prompt)
            elif self.provider == LLMProvider.ANTHROPIC:
                return self._call_anthropic(prompt)
            else:
                raise ValueError(f"Unknown provider: {self.provider}")
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return json.dumps({
                "verdict": "UNVERIFIABLE",
                "confidence": 0.0,
                "reasoning": f"LLM call failed: {str(e)}",
                "citations": [],
                "evidence_grounded": False,
                "grounding_score": 0.0
            })
    
    def _call_openrouter(self, prompt: str) -> str:
        """Call OpenRouter API"""
        import requests
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            },
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"OpenRouter API error: {response.status_code}")
        
        data = response.json()
        return data["choices"][0]["message"]["content"]
    
    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API"""
        import requests
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            },
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"OpenAI API error: {response.status_code}")
        
        data = response.json()
        return data["choices"][0]["message"]["content"]
    
    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API"""
        import requests
        
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "system": self.system_prompt,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            },
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"Anthropic API error: {response.status_code}")
        
        data = response.json()
        return data["content"][0]["text"]
    
    def _parse_response(self, raw_response: str) -> AnalysisResult:
        """Parse LLM JSON response"""
        try:
            # Try to extract JSON from response
            json_match = raw_response.strip()
            
            # Handle markdown code blocks
            if "```json" in json_match:
                json_match = json_match.split("```json")[1].split("```")[0].strip()
            elif "```" in json_match:
                json_match = json_match.split("```")[1].split("```")[0].strip()
            
            data = json.loads(json_match)
            
            return AnalysisResult(
                verdict=data.get("verdict", "UNVERIFIABLE"),
                confidence=float(data.get("confidence", 0.0)),
                reasoning=data.get("reasoning", ""),
                citations=data.get("citations", []),
                evidence_grounded=data.get("evidence_grounded", False),
                grounding_score=float(data.get("grounding_score", 0.0)),
                raw_response=raw_response,
                model_used="",
                temperature=0.0
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return AnalysisResult(
                verdict="UNVERIFIABLE",
                confidence=0.0,
                reasoning=f"Failed to parse LLM response: {raw_response[:200]}",
                citations=[],
                evidence_grounded=False,
                grounding_score=0.0,
                raw_response=raw_response,
                model_used="",
                temperature=0.0
            )
    
    def _verify_grounding(self, result: AnalysisResult, evidence: Dict) -> float:
        """Verify how well the analysis is grounded in evidence"""
        if not result.citations:
            return 0.0
        
        evidence_items = evidence.get("evidence_lines", [])
        if not evidence_items:
            return 0.0
        
        grounded_citations = 0
        for citation in result.citations:
            evidence_id = str(citation.get("evidence_id", ""))
            if evidence_id and any(f"[{evidence_id}]" in item for item in evidence_items):
                grounded_citations += 1
        
        return grounded_citations / len(result.citations) if result.citations else 0.0


def analyze_claim_with_evidence(claim_text: str,
                               claim_language: str,
                               evidence: Dict[str, Any],
                               provider: str = "openrouter") -> AnalysisResult:
    """
    Convenience function for claim analysis
    """
    provider_enum = LLMProvider(provider)
    analyzer = LLMAnalyzer(provider=provider_enum)
    return analyzer.analyze_claim(claim_text, claim_language, evidence)