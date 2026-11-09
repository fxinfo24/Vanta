"""
Master Intelligence Analyzer
Orchestrates the specialized AI analysis modules to generate comprehensive reports.
Integrates Psychological, Consumer, and Belief System intelligence.
"""

import logging
from typing import Dict, Any, List

from .openrouter_client import openrouter_client
from .platform_prompts import get_platform_context

# Specialized Analyzers
from .belief_analyzer import BeliefSystemAnalyzer
from .belief_analyzer import BeliefSystemAnalyzer
from .consumer_intelligence import ConsumerIntelligenceAnalyzer
from .behavioral_analyzer import BehavioralAnalyzer

logger = logging.getLogger(__name__)

class IntelligenceAnalyzer:
    """
    Master Orchestrator for AI Intelligence.
    
    Modules:
    1. Core Intelligence (Psychology, Behavior, Authenticity) - via Platform Prompts
    2. Belief System (Political, Social, Ethical) - via BeliefSystemAnalyzer
    3. Consumer Intelligence (Shopping, Forecasting) - via ConsumerIntelligenceAnalyzer
    """
    
    def __init__(self):
        self.ai = openrouter_client
        self.belief_engine = BeliefSystemAnalyzer(self.ai)
        self.consumer_engine = ConsumerIntelligenceAnalyzer(self.ai)
        self.behavior_engine = BehavioralAnalyzer(self.ai)
        
    def generate_full_report(self, dossier_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a comprehensive intelligence report from a collected dossier.
        """
        logger.info(f"Starting full intelligence analysis for {dossier_data.get('username')}")
        
        report = {
            "meta": {
                "target": dossier_data.get('username'),
                "platform": dossier_data.get('platform'),
                "generated_at": dossier_data.get('collected_at')
            },
            "core_intelligence": {},
            "belief_system": {},
            "belief_system": {},
            "consumer_profile": {},
            "behavioral_profile": {},
            "executive_summary": ""
        }
        
        # 1. CORE INTELLIGENCE (Psych, Behavior, Authenticity, Predictions)
        # This leverages the existing analyze_profile_content logic in OpenRouterClient
        try:
            profile = dossier_data.get('profile', {})
            content = dossier_data.get('content', [])
            deep_data = {
                "demographics": dossier_data.get('demographics'),
                "transcripts": dossier_data.get('transcripts'),
                "comments": dossier_data.get('comments_analysis')
            }
            
            # General Analysis
            report["core_intelligence"]["general_analysis"] = self.ai.analyze_profile_content(
                profile, content, deep_data
            )
            
            # Authenticity
            report["core_intelligence"]["authenticity"] = self.ai.analyze_authenticity(
                profile, report["core_intelligence"]["general_analysis"], content
            )
            
            # Trend Predictions
            report["core_intelligence"]["predictions"] = self.ai.generate_predictions(
                profile, report["core_intelligence"]["general_analysis"]
            )
            
        except Exception as e:
            logger.error(f"Core intelligence failure: {e}")
            report["core_intelligence"]["error"] = str(e)

        # 2. BELIEF SYSTEM ANALYSIS (New Module)
        try:
            report["belief_system"] = self.belief_engine.analyze_belief_system(dossier_data)
        except Exception as e:
            logger.error(f"Belief system failure: {e}")
            report["belief_system"]["error"] = str(e)
            
        # 3. CONSUMER INTELLIGENCE (New Module)
        try:
            report["consumer_profile"] = self.consumer_engine.generate_consumer_profile(dossier_data)
        except Exception as e:
            logger.error(f"Consumer intelligence failure: {e}")
            report["consumer_profile"]["error"] = str(e)
        # 4. BEHAVIORAL ANALYSIS (New Module)
        try:
            report["behavioral_profile"] = self.behavior_engine.analyze_behavior(dossier_data)
        except Exception as e:
            logger.error(f"Behavioral analysis failure: {e}")
            report["behavioral_profile"]["error"] = str(e)

        # 5. EXECUTIVE SUMMARY
        report["executive_summary"] = self._generate_executive_summary(report)
        
        return report

    def _generate_executive_summary(self, report_data: Dict) -> str:
        """Generate a high-level executive summary of the entire report"""
        
        system_prompt = """You are an Intelligence Analyst briefing a stakeholder. 
        You MUST provide your output in valid JSON format with a single key 'summary' containing the text.
        """
        
        prompt = f"""
        Summarize this digital intelligence report into a cohesive narrative.
        
        KEY FINDINGS:
        - Psychology: {json.dumps(report_data.get('core_intelligence', {}).get('general_analysis', {}).get('psychological_profile', 'N/A'))}
        - Politics/Values: {json.dumps(report_data.get('belief_system', {}).get('POLITICAL COMPASS', 'N/A'))}
        - Behavior/Habits: {json.dumps(report_data.get('behavioral_profile', {}).get('interests', 'N/A'))}
        - Consumer Activity: {json.dumps(report_data.get('consumer_profile', {}).get('shopping_psychology', 'N/A'))}
        - Risks: {json.dumps(report_data.get('core_intelligence', {}).get('authenticity', {}).get('risk_assessment', 'N/A'))}
        
        Structure:
        1. Subject Overview (Who are they really?)
        2. Threat/Opporunity Assessment (Risks vs Value)
        3. Predictive Outlook (What will they likely do next?)
        
        Keep it under 300 words. Professional tone.
        
        REQUIRED OUTPUT FORMAT:
        {{
            "summary": "Your executive summary text here..."
        }}
        """
        
        try:
            result = self.ai.analyze(prompt, system_prompt, model_type="general")
            return result.get("summary") or result.get("raw_response") or "Summary generation failed"
        except:
            return "Executive summary could not be generated."

import json

# Convenience factory
def create_intelligence_analyzer() -> IntelligenceAnalyzer:
    return IntelligenceAnalyzer()
