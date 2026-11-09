
import logging
from typing import Dict, Any, List
import json

from .openrouter_client import OpenRouterClient

logger = logging.getLogger(__name__)

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
        
        system_prompt = """
        You are an expert Behavioral Profiler and Psychologist. 
        Analyze the provided social media content to construct a deep behavioral dossier.
        
        You must infer the following attributes with high specificity:
        1. Emotional Temperament (Angry vs Calm, volatile vs stable)
        2. Personal Favorites (Things, People, Hobbies)
        3. Intellectual Habits (Reading, Learning, Tech Expertise)
        4. Lifestyle & Risks (Substance use, Party habits - look for visual/textual cues)
        5. Relationship Dynamics (Attachment style, human relationship patterns)
        6. Professional Capabilities (Skills, Earning Source, Tech Expert status)
        7. Resilience (Compliance vs Resistance, 'Resist or Not')
        
        Output MUST be valid JSON.
        """
        
        prompt = f"""
        Analyze this subject based on their digital footprint:
        
        SUBJECT DATA:
        Username: {profile.get('username')}
        DisplayName: {profile.get('display_name')}
        Platform: {dossier_data.get('platform')}
        
        CONTENT SAMPLES:
        {context_str}
        
        ---------------------------------------------------------
        
        Return a JSON object with this EXACT structure:
        {{
            "temperament": {{
                "label": "Angry" | "Calm" | "Energetic" | "Melancholic" | "Variable",
                "score": 0.0 to 1.0 (intensity),
                "description": "Brief explanation of their emotional baseline."
            }},
            "interests": {{
                "hobbies": ["list", "of", "detected", "hobbies"],
                "favorites": {{
                    "thing": "inferred favorite object/topic",
                    "person": "inferred favorite person/idol"
                }},
                "reading_habit": "Heavy" | "Moderate" | "Light" | "None" | "Unknown",
                "reading_interests": ["genres", "topics"]
            }},
            "professional": {{
                "is_tech_expert": true/false,
                "tech_skill_level": "Novice" | "Competent" | "Expert",
                "earning_source": "Inferred primary income source (e.g. 'Corporate Job', 'Freelance', 'Influencer')",
                "personal_skills": ["skill1", "skill2"],
                "spending_pattern": "Frugal" | "Lavish" | "Strategic" | "Impulsive"
            }},
            "relationships": {{
                "pattern": "Description of how they relate to others (e.g., 'Confrontational', 'Supportive', 'Parasocial')",
                "attachment_style": "Secure" | "Anxious" | "Avoidant" | "Disorganized",
                "sectual_habit_or_dynamic": "Inferred relationship dynamic (e.g., 'Single', 'Partnered', 'Promiscuous', 'Conservative') - KEEP SAFE AND NON-EXPLICIT."
            }},
            "lifestyle_risks": {{
                "drug_alcohol_indicated": true/false,
                "risk_conslusion": "Assessment of substance related risk based on public posts."
            }},
            "psychological_resilience": {{
                "resist_status": "Resistant" | "Compliant",
                "resist_description": "Do they resist authority/norms or comply? Are they resilient to stress?"
            }}
        }}
        """
        
        return self.client.analyze(prompt, system_prompt, model_type="psych")
