"""
OpenRouter LLM Client for Vanta
Universal Large Language Model integration using OpenRouter API
"""

import os
import requests
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
import logging

# Load environment variables
# override=True: a stale shell export of OPENROUTER_API_KEY (old dead key)
# was silently shadowing the updated .env value -> 401 even with a good key.
# .env is the source of truth locally; in prod (no .env file) env vars still apply.
load_dotenv(override=True)

logger = logging.getLogger(__name__)

# Import platform-specific prompts
from .platform_prompts import (
    get_platform_context,
    build_content_analysis_prompt,
    build_authenticity_prompt,
    build_prediction_prompt,
    SUPPORTED_PLATFORMS
)

class OpenRouterError(Exception):
    """OpenRouter API related errors"""
    pass

class OpenRouterClient:
    """Enhanced client for OpenRouter API - Universal LLM Access"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1"
        
        if not self.api_key:
            logger.warning("OpenRouter API key not found. LLM features will be disabled.")
            self.api_key = None
            
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/fxinfo24/Vanta",
            "X-Title": "Vanta Social Media Analysis"
        })
        
        # Available models through OpenRouter
        self.models = {
            "gpt-4": "openai/gpt-4",
            "gpt-4-turbo": "openai/gpt-4-turbo",
            "gpt-3.5-turbo": "openai/gpt-3.5-turbo", 
            "grok-4.1-fast": "x-ai/grok-4.1-fast",  # xAI's best agentic model - 2M context
            "grok-4-fast": "x-ai/grok-4-fast",      # Multimodal with SOTA cost-efficiency
            "grok-code-fast": "x-ai/grok-code-fast-1",  # Specialized for coding
            "nemotron-3-ultra": "nvidia/nemotron-3-ultra-550b-a55b:free",  # Verified live 200
            "nemotron-3.5-super-vl": "nvidia/nemotron-3.5-super-vl:free",  # Verified live 200, vision
            "gemini-pro": "google/gemini-pro",
            "llama-2-70b": "meta-llama/llama-2-70b-chat",
            "mixtral-8x7b": "mistralai/mixtral-8x7b-instruct"
        }
        
        # Default model for different analysis types
        # Configurable via OPENROUTER_MODEL env (fallback: Nemotron 3 Ultra free,
        # verified live 200). Grok remains available via self.models.
        _m = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
        self.default_models = {k: _m for k in [
            "content_analysis", "personality_analysis", "authenticity_analysis",
            "sentiment_analysis", "trend_analysis", "belief_analysis",
            "consumer_analysis", "psych", "general"]}
    
    def analyze(self, prompt: str, system_prompt: str = None, model_type: str = "general") -> Dict[str, Any]:
        """
        Generic analysis method for external analyzers.
        Returns parsed JSON response.
        """
        if not system_prompt:
            system_prompt = "You are an expert analyst. Provide output in valid JSON format."
            
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        model = self.default_models.get(model_type, self.default_models["general"])
        
        try:
            response = self._make_request(
                messages=messages,
                model=model,
                temperature=0.3, # Low temp for structured data
                max_tokens=3000
            )
            
            # Auto-clean markdown
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.startswith("```"):
                clean_response = clean_response[3:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
                
            return json.loads(clean_response)
            
        except json.JSONDecodeError as e:
            logger.error(f"Generic analysis JSON parse failed: {e}")
            return {"error": "JSON parse error", "raw_response": clean_response}
        except Exception as e:
            logger.error(f"Generic analysis failed: {e}")
            return {"error": str(e)}
    
    def _make_request(self, messages: List[Dict[str, str]], model: str = None, 
                     temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """Make request to OpenRouter API"""
        if not self.api_key:
             raise OpenRouterError("OpenRouter API key not configured")

        if not model:
            model = self.default_models["general"]
            
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=60
            )
            
            if response.status_code == 429:
                raise OpenRouterError("Rate limit exceeded")
            elif response.status_code == 401:
                raise OpenRouterError("Invalid API key")
            elif response.status_code != 200:
                raise OpenRouterError(f"API error: {response.status_code} - {response.text}")
                
            result = response.json()
            return result["choices"][0]["message"]["content"]
            
        except requests.RequestException as e:
            raise OpenRouterError(f"Request failed: {str(e)}")
        except (KeyError, IndexError) as e:
            raise OpenRouterError(f"Invalid response format: {str(e)}")
    
    def analyze_profile_content(self, profile_data: Dict[str, Any], posts: List[Dict[str, Any]], deep_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Comprehensive profile content analysis using platform-specific prompts"""
        
        # Get platform from profile data
        platform = profile_data.get('platform', profile_data.get('metadata', {}).get('platform', 'twitter'))
        
        # Build platform-optimized prompt
        user_prompt = build_content_analysis_prompt(platform, profile_data, posts)
        
        # Enhanced Vanta Context: Inject Deep Data
        if deep_data:
            user_prompt += f"\n\nDEEP ANALYSIS DATA (Transcripts, Comments, Demographics):\n{json.dumps(deep_data, indent=2, default=str)}\n\nUse this deep data to infer psychological traits, audience demographics, and hidden behavioral patterns."
        ctx = get_platform_context(platform)
        
        messages = [
            {
                "role": "system",
                "content": f"""You are an expert {ctx['name']} analyst and social media forensics specialist.
You specialize in analyzing profiles on {ctx['name']} and understanding its unique culture, algorithm, and user behaviors.
You MUST return your analysis as valid JSON only - no markdown, no explanations, just the JSON object.
Return comprehensive, platform-specific insights that leverage {ctx['name']}'s unique characteristics."""
            },
            {
                "role": "user", 
                "content": user_prompt
            }
        ]
        
        try:
            response = self._make_request(
                messages=messages,
                model=self.default_models["content_analysis"],
                temperature=0.3,
                max_tokens=3500
            )
            
            # Clean response if needed (remove markdown code blocks)
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.startswith("```"):
                clean_response = clean_response[3:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            
            # Parse JSON response
            analysis = json.loads(clean_response.strip())
            analysis["_platform"] = platform
            analysis["_model_used"] = self.default_models["content_analysis"]
            return analysis
            
        except json.JSONDecodeError as e:
            # Fallback if JSON parsing fails
            logger.warning(f"Failed to parse JSON response for {platform}: {e}")
            return {
                "error": "Failed to parse structured response",
                "raw_analysis": response,
                "content_themes": ["analysis_available"],
                "key_insights": ["Raw analysis available in raw_analysis field"],
                "_platform": platform
            }
        except Exception as e:
            logger.error(f"Content analysis failed for {platform}: {e}")
            raise OpenRouterError(f"Analysis failed: {str(e)}")
    
    def analyze_authenticity(self, profile_data: Dict[str, Any], content_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticity analysis using Grok 4.1 Fast"""
        
        profile_metrics = f"""
Username: @{profile_data.get('username')}
Account Age: {profile_data.get('created_at', 'Unknown')}
Followers: {profile_data.get('followers_count', 0):,}
Following: {profile_data.get('following_count', 0):,}
Posts: {profile_data.get('posts_count', 0):,}
Verified: {profile_data.get('verified', False)}
Bio Length: {len(profile_data.get('bio', ''))} characters
Profile Image: {'Present' if profile_data.get('profile_image_url') else 'Missing'}
        """.strip()
        
        content_summary = json.dumps(content_analysis.get('key_insights', []), indent=2)
        
        messages = [
            {
                "role": "system",
                "content": """You are a cybersecurity expert specializing in fake account detection and 
                social media authenticity analysis. Analyze profiles for signs of automation, bot behavior, 
                purchased followers, and other authenticity issues.
                CRITICAL: If 'Verified' is True, start with a high base trust score (>0.8) unless you find specific evidence of compromise (hacked verified account)."""
            },
            {
                "role": "user",
                "content": f"""Analyze this profile for authenticity:

PROFILE METRICS:
{profile_metrics}

CONTENT ANALYSIS INSIGHTS:
{content_summary}

Provide authenticity analysis in JSON format:
1. overall_authenticity: Object with score (0-1) and confidence (0-1)
2. bot_likelihood: Score 0-1 indicating automated behavior probability
3. engagement_authenticity: Analysis of follower/engagement quality
4. content_authenticity: Analysis of human vs AI-generated content
5. account_age_analysis: Relationship between account age and metrics
6. red_flags: Array of concerning indicators found
7. green_flags: Array of positive authenticity indicators
8. recommendations: Array of verification steps to confirm authenticity
9. risk_assessment: String level (low/medium/high/critical)

Be thorough in detecting fake accounts, bot networks, and purchased engagement."""
            }
        ]
        
        try:
            response = self._make_request(
                messages=messages,
                model=self.default_models["authenticity_analysis"],
                temperature=0.2,
                max_tokens=2000
            )
            
            # Clean possible markdown
            clean_response = response.strip()
            if clean_response.startswith("```json"): clean_response = clean_response[7:]
            if clean_response.startswith("```"): clean_response = clean_response[3:]
            if clean_response.endswith("```"): clean_response = clean_response[:-3]

            return json.loads(clean_response)
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse authenticity analysis JSON: {e}")
            return {
                "overall_authenticity": {"score": 0.5, "confidence": 0.3},
                "error": "Failed to parse structured response",
                "raw_response": response
            }
        except Exception as e:
            logger.error(f"Authenticity analysis failed: {e}")
            raise OpenRouterError(f"Authenticity analysis failed: {str(e)}")
    
    def generate_predictions(self, profile_data: Dict[str, Any], content_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate future predictions using advanced reasoning"""
        
        messages = [
            {
                "role": "system", 
                "content": """You are a data scientist specializing in social media trend prediction and 
                behavioral forecasting. Generate data-driven predictions about future account behavior, 
                growth patterns, and content evolution."""
            },
            {
                "role": "user",
                "content": f"""Based on this profile analysis, generate predictions:

PROFILE: @{profile_data.get('username')}
PLATFORM: {profile_data.get('platform')}
CURRENT METRICS: {profile_data.get('followers_count', 0):,} followers, {profile_data.get('posts_count', 0):,} posts
CONTENT THEMES: {content_analysis.get('content_themes', [])}
ENGAGEMENT STYLE: {content_analysis.get('audience_engagement', {})}

Generate predictions in JSON format:
1. growth_forecast: Object with 30/90/365 day follower predictions
2. content_evolution: Predicted changes in posting themes/style  
3. engagement_trends: Expected engagement rate changes
4. viral_potential: Likelihood of creating viral content (0-1)
5. platform_expansion: Recommended other platforms to join
6. optimal_posting: Best times/frequency for maximum engagement
7. collaboration_opportunities: Types of partnerships that would work
8. risk_factors: Potential reputation or growth risks
9. success_probability: Overall likelihood of continued growth (0-1)
10. actionable_insights: Specific recommendations for improvement

Base predictions on observable patterns and industry benchmarks."""
            }
        ]
        
        try:
            response = self._make_request(
                messages=messages,
                model=self.default_models["trend_analysis"],
                temperature=0.4,
                max_tokens=2500
            )
            
            return json.loads(response)
            
        except json.JSONDecodeError:
            logger.warning("Failed to parse predictions JSON")
            return {
                "growth_forecast": {"30_day": 0, "90_day": 0, "365_day": 0},
                "error": "Failed to parse structured response"
            }
        except Exception as e:
            logger.error(f"Prediction generation failed: {e}")
            raise OpenRouterError(f"Prediction generation failed: {str(e)}")
    
    def get_quick_summary(self, profile_data: Dict[str, Any]) -> str:
        """Generate a quick human-readable summary"""
        
        messages = [
            {
                "role": "system",
                "content": "You are a social media expert. Provide concise, insightful summaries of social media profiles."
            },
            {
                "role": "user", 
                "content": f"""Provide a 2-3 sentence summary of this profile:

@{profile_data.get('username')} - {profile_data.get('display_name')}
Bio: {profile_data.get('bio', 'No bio')}
{profile_data.get('followers_count', 0):,} followers on {profile_data.get('platform', 'unknown')}
Verified: {profile_data.get('verified', False)}

Make it informative and engaging, highlighting the most interesting aspects."""
            }
        ]
        
        try:
            return self._make_request(
                messages=messages,
                model=self.default_models["general"],
                temperature=0.6,
                max_tokens=150
            )
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return f"Profile analysis for @{profile_data.get('username')} on {profile_data.get('platform')}."

# Create singleton instance
openrouter_client = OpenRouterClient()