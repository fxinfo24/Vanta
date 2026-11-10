"""
Consumer Intelligence Analyzer
Analyzes purchase behavior, brand affinity, and forecasts future spending.
"""

import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class ConsumerIntelligenceAnalyzer:
    """
    Analyzes consumer behavior, brand affinity, and purchase intent.
    Provides forecasting for future purchases.
    """
    
    def __init__(self, openrouter_client):
        self.ai = openrouter_client

    def generate_consumer_profile(self, all_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive AI-generated consumer intelligence report.
        """
        
        # Extract commerce-specific signals
        commerce_signals = self._extract_commerce_signals(all_data)

        # No signals means the model can only invent a persona, so the call is
        # skipped and the empty result says why. This is the same rule the
        # authenticity verdict follows when a run collected nothing.
        if not any(commerce_signals.values()):
            logger.info("No commerce signals in the dossier; consumer analysis skipped")
            return {
                "current_usage": {"products": [], "brands": []},
                "shopping_psychology": {},
                "brand_relationships": {"brand_loyalty": {}, "category_preferences": []},
                "purchase_intent": {"active_consideration": [], "wishlist": []},
                "forecast_90_day": {"predicted_purchases": [], "confidence": [], "reasoning": []},
                "marketing_profile": {"price_sensitivity": "", "influence_susceptibility": None},
                "evidence": [],
                "limitations": ("No purchase, brand or product signals were found in the collected "
                                "posts, so no consumer profile was generated."),
            }

        system_prompt = """You are a Consumer Psychologist and Marketing Intelligence Expert.
        Analyze digital footprints to construct high-fidelity consumer profiles and purchase forecasts."""
        
        prompt = f"""
        Analyze this person's complete digital footprint and generate a 
        comprehensive consumer intelligence profile.
        
        DATA SIGNALS:
        {json.dumps(commerce_signals, indent=2)}
        
        Provide analysis in this JSON structure:
        
        1. current_usage:
           - products: List of products confirmed in use
           - brands: List of brands interacted with
           
        2. shopping_psychology:
           - buyer_persona: "Impulse", "Researcher", "Deal Hunter", "Luxury Connoisseur"
           - decision_drivers: ["Price", "Aesthetics", "Ethics", "Status"]
           - adoption_curve: "Innovator", "Early Adopter", "Majority", "Laggard"
           
        3. brand_relationships:
           - brand_loyalty: {{ "Apple": "High", "Nike": "Medium" }}
           - category_preferences: preferred categories
           
        4. purchase_intent:
           - active_consideration: Products they are currently researching
           - wishlist: Items saved or mentioned as "want"
           
        5. forecast_90_day:
           - predicted_purchases: List of specific objects likely to be bought
           - confidence: 0-1 score for each prediction
           - reasoning: Evidence-based logic        6. marketing_profile:
           - price_sensitivity: "Low", "Medium", "High"
           - influence_susceptibility: 0-10 (How likely to buy from ad/influencer)

        7. evidence: List of receipts, one per material claim:
           - claim: the specific claim (e.g. "current_usage.brands: Microsoft")
           - quote: EXACT text copied from DATA SIGNALS - no paraphrase

        EVIDENCE RULES: every brand, product and predicted purchase must be backed by
        at least one verbatim quote. Receipts that do not match the supplied signals are
        discarded, taking the claim with them. If the signals contain no commerce
        material at all, return empty lists and say so in `limitations` rather than
        inventing a shopping persona.

        Format as pure JSON.
        """
        
        return self.ai.analyze(prompt, system_prompt, model_type="consumer_analysis")
        
    def _extract_commerce_signals(self, data: Dict) -> Dict:
        """Extract data likely to contain purchase signals"""
        signals = {
            "shopping_activity": [],
            "product_mentions": [],
            "lifestyle_indicators": [] # For inferring budget/class
        }
        
        # 1. Direct Commerce Data (TikTok Shop, Amazon)
        if data.get('shop_products'):
            signals['shopping_activity'].extend(data['shop_products'])
            
        # 2. Content mentions (Looking for "bought", "review", "unboxing")
        for item in data.get('content', []):
            text = (item.get('text') or item.get('caption') or item.get('description') or "").lower()
            
            # Simple keyword filter to reduce noise
            keywords = ['bought', 'buy', 'purchased', 'got this', 'review', 'unboxing', 'haul', 'obsessed with', 'link in bio', 'code']
            if any(k in text for k in keywords):
                signals['product_mentions'].append({
                    "text": text[:500],
                    "platform": item.get('platform', 'unknown'),
                    "date": item.get('created_at', 'unknown')
                })
                
        return signals
