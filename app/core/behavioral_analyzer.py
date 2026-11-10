
import logging
from typing import Dict, Any, List
import json

from .openrouter_client import OpenRouterClient
from ..utils.config import allows_special_category_inference
from ..utils.helpers import identity_description

logger = logging.getLogger(__name__)

# Sections that infer Art. 9 categories: intimate relationships (sex life),
# substance use (health). They are requested only when the deployment has
# explicitly enabled special-category inference.
GATED_SECTIONS = ("relationships", "lifestyle_risks")


_SCHEMA_TEMPLATE = """{
    "temperament": {
        "label": "Angry" | "Calm" | "Energetic" | "Melancholic" | "Variable",
        "score": 0.0 to 1.0 (intensity),
        "description": "Brief explanation of their emotional baseline."
    },
    "interests": {
        "hobbies": ["list", "of", "detected", "hobbies"],
        "favorites": {
            "thing": "inferred favorite object/topic",
            "person": "inferred favorite person/idol"
        },
        "reading_habit": "Heavy" | "Moderate" | "Light" | "None" | "Unknown",
        "reading_interests": ["genres", "topics"]
    },
    "professional": {
        "is_tech_expert": true,
        "tech_skill_level": "Novice" | "Competent" | "Expert",
        "earning_source": "Inferred primary income source (e.g. 'Corporate Job', 'Freelance', 'Influencer')",
        "personal_skills": ["skill1", "skill2"],
        "spending_pattern": "Frugal" | "Lavish" | "Strategic" | "Impulsive"
    },
{GATED}    "psychological_resilience": {
        "resist_status": "Resistant" | "Compliant",
        "resist_description": "Do they resist authority/norms or comply? Are they resilient to stress?"
    },
    "evidence": [
        {"claim": "temperament=Angry", "quote": "EXACT text copied from CONTENT SAMPLES above"}
    ]
}"""

_GATED_SCHEMA = """    "relationships": {
        "pattern": "Description of how they relate to others (e.g., 'Confrontational', 'Supportive', 'Parasocial')",
        "attachment_style": "Secure" | "Anxious" | "Avoidant" | "Disorganized",
        "relationship_dynamic": "Inferred relationship status/dynamic (e.g., 'Single', 'Partnered') - KEEP SAFE AND NON-EXPLICIT."
    },
    "lifestyle_risks": {
        "drug_alcohol_indicated": false,
        "risk_conclusion": "Assessment of substance related risk based on public posts."
    },
"""


# The gate is permanent for third-party subjects: there is no consent to point at,
# so the inference is never run. The payload carries a machine-readable code and a
# plain-language reason; internal config keys are not part of the API surface, since
# anything here is also visible in exports and to any API consumer.
GATED_CODE = "special_category_not_inferred"
GATED_REASON = ("Not inferred. This section would describe sensitive personal attributes "
                "of someone who has not agreed to being analysed.")


def gated_notice() -> Dict[str, Any]:
    """The one shape every policy-gated section uses (behavioral and belief)."""
    return {
        "gated": True,
        "status": "not_collected",
        "code": GATED_CODE,
        "reason": GATED_REASON,
    }

class BehavioralAnalyzer:
    """
    Analyzes deep behavioral traits, lifestyle habits, and psychological patterns.
    Covers:
    - Temperament (Angry/Calm)
    - Hobbies & Interests
    - Professional Skills & Tech Expertise
    - Relationship Patterns
    - Resilience & Resistance
    - Lifestyle Risks (Substance use indicators)
    """
    
    def __init__(self, client: OpenRouterClient):
        self.client = client
        
    def analyze_behavior(self, dossier_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a deep behavioral profile based on digital footprint.
        """
        logger.info(f"Starting behavioral analysis for {dossier_data.get('username')}")
        
        # Prepare context (older/partial dossiers may store profile: None)
        profile = dossier_data.get('profile') or {}
        content = dossier_data.get('content') or []
        bio = profile.get('bio', '') or profile.get('description', '')
        
        # Extract text samples for analysis (limit to prevent token overflow)
        text_samples = []
        if bio:
            text_samples.append(f"BIO: {bio}")
            
        for item in content[:20]: # Analyze top 20 items
            text = item.get('text') or item.get('description') or item.get('caption') or ''
            if text:
                text_samples.append(f"POST: {text[:300]}")
                
        # Add transcript snippets if available
        transcripts = dossier_data.get('transcripts', [])
        for t in transcripts[:3]:
            text = t.get('transcript', {}).get('text', '')
            if text:
                text_samples.append(f"TRANSCRIPT_SNIPPET: {text[:500]}")
                
        context_str = "\n".join(text_samples)
        allow_special = allows_special_category_inference()
        
        system_prompt = """
        You are an expert Behavioral Profiler and Psychologist. 
        Analyze the provided social media content to construct a deep behavioral dossier.
        
        You must infer the following attributes with high specificity:
        1. Emotional Temperament (Angry vs Calm, volatile vs stable)
        2. Personal Favorites (Things, People, Hobbies)
        3. Intellectual Habits (Reading, Learning, Tech Expertise)
        4. Professional Capabilities (Skills, Earning Source, Tech Expert status)
        5. Resilience (Compliance vs Resistance, 'Resist or Not')
        """
        if allow_special:
            system_prompt += """        6. Lifestyle & Risks (Substance use, Party habits - look for visual/textual cues)
        7. Relationship Dynamics (Attachment style, human relationship patterns)
"""
        system_prompt += "        \n        Output MUST be valid JSON.\n        """

        schema = _SCHEMA_TEMPLATE.replace(
            "{GATED}", _GATED_SCHEMA if allow_special else ""
        )
        gated_note = ("" if allow_special else
                      "\n        Do NOT infer substance use, health conditions or intimate-relationship "
                      "patterns: those sections are disabled by policy and must be omitted.\n")

        prompt = f"""
        Analyze this subject based on their digital footprint:
        
        SUBJECT DATA:
        {identity_description(profile)}
        Platform: {dossier_data.get('platform')}
        
        CONTENT SAMPLES:
        {context_str}
        
        ---------------------------------------------------------
        
        Return a JSON object with this EXACT structure:
        {schema}
{gated_note}
        EVIDENCE RULES: every section above must have at least one entry in `evidence`.
        Each `quote` must be copied character-for-character from CONTENT SAMPLES - no
        paraphrase, no translation, no stitching of two posts. A receipt that cannot be
        matched to the samples is discarded, so an unsupported section reads as
        unsupported rather than as a finding.
        """
        
        result = self.client.analyze(prompt, system_prompt, model_type="psych")
        if isinstance(result, dict) and not allow_special:
            # A model that volunteers a gated attribute anyway does not get to keep it.
            for section in GATED_SECTIONS:
                result.pop(section, None)
                result[section] = gated_notice()
            result.setdefault("limitations", [])
            if isinstance(result["limitations"], list):
                result["limitations"].append(
                    "Relationships and substance use are not inferred: they describe sensitive "
                    "personal attributes of someone who has not agreed to being analysed."
                )
        return result
