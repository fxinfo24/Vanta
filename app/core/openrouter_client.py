"""
OpenRouter LLM Client for Vanta
Universal Large Language Model integration using OpenRouter API
"""

import os
import re
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
    SUPPORTED_PLATFORMS,
    _content_availability,
    _boundary_text,
)

class OpenRouterError(Exception):
    """OpenRouter API related errors"""
    pass


# ---------------------------------------------------------------------------
# Authenticity grounding
# ---------------------------------------------------------------------------
# An indicator is only admissible if the dimension it reasons about was
# actually collected. Availability is COMPUTED from the samples (a deep
# Facebook dossier does carry reaction/share/comment counts and video/image
# metadata) instead of being hardcoded per platform, and a deterministic pass
# then removes indicators that assert something about a dimension with no
# data behind it. Prompt constraints alone were not enforced often enough.

# dimension -> (label, trigger pattern). The label is what the user sees when
# an indicator is dropped for lack of data.
_DIMENSION_TERMS = {
    "engagement": (
        "engagement/reach",
        r"\bengagement\b|\breach\b|\bimpressions?\b|\bshadow-?ban|\bsuppress\w*"
        r"|\bviral\b|\breactions?\b|\bshares?\b|\blikes?\b|\bviews?\b",
    ),
    "media": (
        "video/image metadata",
        r"\breels?\b|\bvideos?\b|\blive\s?streams?\b|\bmultimedia\b|\bphotos?\b"
        r"|\bimages?\b|\bvisual\w*|\bcarousel\b|\bstories\b",
    ),
    "network": (
        "follower/following network data",
        r"\bcoordinated\b|\bbot\s+network|\bnetwork\s+of\b|\bfollow[- ]for[- ]follow\b"
        r"|\breciprocal\w*|\bfollower\s+farm|\bastroturf\w*|\btroll\s+farm"
        r"|\binauthentic\s+(behavio\w*|activity)|\bpurchased\s+(followers?|engagement)",
    ),
    "demographics": (
        "audience demographic data",
        r"\bdemograph\w*|\bgender\w*|\bmales?\b|\bfemales?\b|\bage\s+(range|bracket|group|distribution)"
        r"|\baudience\s+(is|are|composition|skew)|\bcommenters?\s+(are|is|skew)",
    ),
    "groups": (
        "group membership data",
        r"\bgroups?\b|\bcommunities\b",
    ),
}

# Phrases about the profile picture are a profile metric, not content media.
_PROFILE_IMAGE_RE = re.compile(r"profile\s+(image|picture)|avatar", re.IGNORECASE)


# "There is none of X" where X demonstrably exists in the samples.
_ABSENCE_RE = re.compile(
    r"\b(no|zero|none|never|lacks?|lacking|without|absent|missing|not?\s+any)\b", re.IGNORECASE
)
_MEDIA_PRESENT_RE = re.compile(r"\breels?\b|\bvideos?\b|\bmultimedia\b|\blive\b", re.IGNORECASE)


def _normalize_text(value: Any) -> str:
    """Case/whitespace-insensitive form used to prove a quote is verbatim."""
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _validate_topical_focus(result: Dict[str, Any], content_items: Optional[List[Any]]) -> Dict[str, Any]:
    """Ground the topical description in verbatim samples.

    A niche - political or otherwise - is an observable property of the posts,
    so it is reported as a fact. It is deliberately NOT a risk signal: topic
    alone says nothing about whether an account is authentic. Any evidence
    quote the model paraphrased rather than copied is removed here, because an
    unverifiable quote is the same defect as an invented one.
    """
    if not isinstance(result, dict):
        return result
    focus = result.get("topical_focus")
    if not isinstance(focus, dict):
        return result

    texts = []
    for item in content_items or []:
        if isinstance(item, dict):
            texts.append(_normalize_text(item.get("text") or item.get("content") or ""))
    corpus = "\n".join(texts)

    raw_evidence = focus.get("evidence")
    kept, dropped = [], []
    for quote in raw_evidence if isinstance(raw_evidence, list) else []:
        probe = _normalize_text(quote)
        # Short fragments match too often to prove anything.
        if len(probe) >= 8 and probe in corpus:
            kept.append(quote)
        else:
            dropped.append(quote)

    focus["evidence"] = kept
    focus["evidence_verified"] = bool(kept)
    focus["evidence_provided"] = len(kept) + len(dropped)

    intensity = focus.get("political_intensity")
    try:
        focus["political_intensity"] = max(0.0, min(1.0, float(intensity)))
    except (TypeError, ValueError):
        focus["political_intensity"] = None

    if not isinstance(focus.get("primary_topic"), str) or not focus["primary_topic"].strip():
        focus["primary_topic"] = "Unknown"

    if dropped:
        limitations = result.get("limitations")
        if not isinstance(limitations, list):
            limitations = [limitations] if limitations else []
        limitations.append(
            f"{len(dropped)} topical quote(s) were removed because they do not appear "
            "verbatim in the collected posts."
        )
        result["limitations"] = limitations

    result["topical_focus"] = focus
    return result



def _filter_unbacked_flags(flags: Any, avail: Dict[str, Any]) -> tuple:
    """Drop indicators the collected samples cannot support.

    Two rejection reasons:
      * the dimension the indicator reasons about was never collected;
      * the indicator asserts absence of something the samples demonstrably
        contain (e.g. "no multimedia" while 11 reels were collected).

    Returns ``(kept_flags, dropped_flags, reason_labels)`` so the caller can
    record the removal instead of applying it silently.
    """
    kept, dropped, reasons = [], [], set()
    for flag in flags or []:
        text = flag if isinstance(flag, str) else json.dumps(flag, ensure_ascii=False)
        lowered = text.lower()
        reason = None

        if avail["video_items"] and _ABSENCE_RE.search(text) and _MEDIA_PRESENT_RE.search(text):
            reason = "contradicted by collected video/image data"
        else:
            for dimension, (label, pattern) in _DIMENSION_TERMS.items():
                if avail.get(f"has_{dimension}"):
                    continue
                if dimension == "media" and _PROFILE_IMAGE_RE.search(text):
                    # Mentions the profile picture only: that is a profile metric,
                    # not content media.
                    if not _MEDIA_PRESENT_RE.search(text):
                        continue
                if re.search(pattern, lowered):
                    reason = label
                    break

        if reason:
            dropped.append(flag)
            reasons.add(reason)
        else:
            kept.append(flag)
    return kept, dropped, reasons


def _apply_flag_grounding(result: Dict[str, Any], avail: Dict[str, Any]) -> Dict[str, Any]:
    """Filter indicators and record any removal in ``limitations``."""
    if not isinstance(result, dict) or "error" in result:
        return result
    dropped_all: List[str] = []
    reasons: set = set()
    for key in ("red_flags", "green_flags"):
        kept, dropped, why = _filter_unbacked_flags(result.get(key), avail)
        if key in result or kept:
            result[key] = kept
        dropped_all.extend(dropped)
        reasons |= why
    if dropped_all:
        result["filtered_indicators"] = dropped_all
        limitations = result.get("limitations")
        if not isinstance(limitations, list):
            limitations = [limitations] if limitations else []
        limitations.append(
            f"{len(dropped_all)} indicator(s) were discarded: they relied on "
            f"{'; '.join(sorted(reasons))}."
        )
        result["limitations"] = limitations
    return result


def _filter_unsupported_claims(claims: Any, avail: Dict[str, Any], label: str = "insight") -> tuple:
    """Apply the same grounding test to prose claims (content key_insights).

    Text insight lists fabricate in exactly the same way flags do - "algorithmic
    suppression", "zero group participation" - so they are held to the same
    rule instead of relying on the prompt alone.
    """
    kept, dropped, reasons = _filter_unbacked_flags(claims, avail)
    if dropped:
        logger.info(f"Discarded {len(dropped)} unsupported {label}(s): {sorted(reasons)}")
    return kept, dropped, reasons


class OpenRouterClient:
    """Enhanced client for OpenRouter API - Universal LLM Access"""

    def __init__(self, api_key=None):
        # Explicit key wins; otherwise resolve per-request (BYOK user key
        # -> server env) so the module-level singleton stays safe across
        # concurrent users. The Authorization header is refreshed in
        # _make_request, never baked from stale state.
        from app.utils.config import resolve_api_key
        self._explicit_key = api_key
        self.api_key = api_key or resolve_api_key("OPENROUTER_API_KEY")
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
        # Default model for different analysis types; resolved per access so
        # a user's preferred model (BYOK settings) applies to THIS request.
        # Kept as a property (not an init-baked dict) for context safety.
        self._model_keys = [
            "content_analysis", "personality_analysis", "authenticity_analysis",
            "sentiment_analysis", "trend_analysis", "belief_analysis",
            "consumer_analysis", "psych", "general"]

    def _refresh_auth(self):
        """Re-resolve the key for the current execution context."""
        from app.utils.config import resolve_api_key
        self.api_key = self._explicit_key or resolve_api_key("OPENROUTER_API_KEY")
        if self.api_key:
            self.session.headers["Authorization"] = f"Bearer {self.api_key}"

    @property
    def default_models(self):
        from app.utils.config import resolve_openrouter_model
        _m = resolve_openrouter_model()
        return {k: _m for k in self._model_keys}

    @staticmethod
    def _clean_json_text(text: str) -> str:
        """Strip markdown fences from an LLM completion, keeping the JSON body."""
        clean = (text or "").strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        return clean.strip()

    @staticmethod
    def _parse_json(clean_text: str) -> Any:
        """Parse JSON, falling back to the first-to-last-brace span
        (models sometimes wrap JSON in prose)."""
        try:
            return json.loads(clean_text)
        except json.JSONDecodeError:
            start = clean_text.find("{")
            end = clean_text.rfind("}")
            if start != -1 and end > start:
                return json.loads(clean_text[start:end + 1])
            raise

    @staticmethod
    def _is_truncation_error(err: json.JSONDecodeError) -> bool:
        """Heuristics for output cut off by max_tokens:
        the JSON ends mid-structure instead of being malformed."""
        msg = str(err)
        return any(sig in msg for sig in (
            "Expecting ',' delimiter",
            "Expecting property name enclosed in double quotes",
            "Unterminated string",
            "Expecting value",
            "Expecting ':' delimiter",
        ))

    def _request_json(self, messages: List[Dict[str, str]], model: str, temperature: float,
                      max_tokens: int, label: str = "analysis") -> Any:
        """Request a JSON completion with the recovery paths every caller needs.

        Empty completion -> one retry. Truncated JSON -> one re-request at double
        budget (capped). Anything still unparseable raises JSONDecodeError so the
        caller reports absence instead of inventing defaults.
        """
        response = self._make_request(
            messages=messages, model=model, temperature=temperature, max_tokens=max_tokens
        ) or ""
        if not response.strip():
            logger.warning(f"Empty completion for {label}, retrying once")
            response = self._make_request(
                messages=messages, model=model, temperature=temperature, max_tokens=max_tokens
            ) or ""
        if not response.strip():
            raise ValueError(f"Empty LLM response for {label} after retry")

        try:
            return self._parse_json(self._clean_json_text(response))
        except json.JSONDecodeError as e:
            if not self._is_truncation_error(e):
                raise
            logger.warning(f"Truncated JSON for {label} ({e}); retrying with larger max_tokens")
            retry = self._make_request(
                messages=messages, model=model, temperature=temperature,
                max_tokens=min(max_tokens * 2, 12000),
            ) or ""
            if not retry.strip():
                raise
            return self._parse_json(self._clean_json_text(retry))

    def analyze(self, prompt: str, system_prompt: str = None, model_type: str = "general", max_tokens: int = 6000) -> Dict[str, Any]:
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
                max_tokens=max_tokens  # Nemotron reasoning models burn tokens thinking; 3000 truncates long JSON
            ) or ""
            # Nemotron occasionally returns an empty completion; one retry
            # turns a hard parse failure into a clean result on transient empties.
            if not response.strip():
                logger.warning(f"Empty completion for model_type={model_type}, retrying once")
                response = self._make_request(
                    messages=messages,
                    model=model,
                    temperature=0.3,
                    max_tokens=max_tokens
                ) or ""
            if not response.strip():
                raise ValueError(f"Empty LLM response for model_type={model_type} after retry")
            
            clean_response = self._clean_json_text(response)
            try:
                return self._parse_json(clean_response)
            except json.JSONDecodeError as e:
                # Truncated output (hit max_tokens mid-JSON) is recoverable:
                # re-request ONCE with double the token budget.
                if self._is_truncation_error(e):
                    logger.warning(f"Truncated JSON for model_type={model_type} ({e}); retrying with larger max_tokens")
                    retry = self._make_request(
                        messages=messages,
                        model=model,
                        temperature=0.3,
                        max_tokens=min(max_tokens * 2, 12000)
                    ) or ""
                    if retry.strip():
                        return self._parse_json(self._clean_json_text(retry))
                raise
            
        except json.JSONDecodeError as e:
            logger.error(f"Generic analysis JSON parse failed: {e}")
            return {"error": "JSON parse error", "raw_response": clean_response}
        except Exception as e:
            logger.error(f"Generic analysis failed: {e}")
            return {"error": str(e)}
    
    def _make_request(self, messages: List[Dict[str, str]], model: str = None, 
                     temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """Make request to OpenRouter API"""
        self._refresh_auth()  # per-request key (BYOK context -> env)
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
            return result["choices"][0]["message"].get("content") or ""
            
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
            user_prompt += (
                f"\n\nDEEP ANALYSIS DATA (Transcripts, Comments, Demographics):\n"
                f"{json.dumps(deep_data, indent=2, default=str)}\n\n"
                "Use this deep data only to the extent it actually covers something: transcripts for "
                "spoken content, comments for audience reaction. A handful of comments is not an "
                "audience sample - do not generalise demographics or draw behavioural conclusions "
                "beyond what is shown."
            )
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
            analysis = self._request_json(
                messages,
                model=self.default_models["content_analysis"],
                temperature=0.3,
                max_tokens=3500,
                label=f"content_analysis:{platform}",
            )
            analysis["_platform"] = platform
            analysis["_model_used"] = self.default_models["content_analysis"]

            # Insights carry the same fabrication risk as authenticity flags:
            # hold them to the dimensions this collection actually covers.
            avail = _content_availability(posts, profile_data)
            kept, dropped, reasons = _filter_unsupported_claims(
                analysis.get("key_insights"), avail
            )
            if isinstance(analysis.get("key_insights"), list):
                analysis["key_insights"] = kept
            if dropped:
                analysis["filtered_insights"] = dropped
                limitations = analysis.get("limitations")
                if not isinstance(limitations, list):
                    limitations = [limitations] if limitations else []
                limitations.append(
                    f"{len(dropped)} insight(s) were discarded: they relied on "
                    f"{'; '.join(sorted(reasons))}."
                )
                analysis["limitations"] = limitations
            return analysis
            
        except (json.JSONDecodeError, ValueError) as e:
            # No usable structure: report that, rather than placing placeholder
            # themes/insights that would be read as findings.
            logger.warning(f"Content analysis unavailable for {platform}: {e}")
            return {
                "error": "Analysis could not be generated in this run",
                "content_themes": [],
                "key_insights": [],
                "limitations": [
                    "The content analysis did not produce usable output; the related "
                    "tabs are empty rather than filled with placeholder findings."
                ],
                "_platform": platform,
            }
        except Exception as e:
            logger.error(f"Content analysis failed for {platform}: {e}")
            raise OpenRouterError(f"Analysis failed: {str(e)}")
    
    def analyze_authenticity(self, profile_data: Dict[str, Any], content_analysis: Dict[str, Any],
                             content_items: Optional[List[Any]] = None) -> Dict[str, Any]:
        """Authenticity analysis using Grok 4.1 Fast"""
        
        # Dossiers store 'follower_count' (singular); some clients use
        # 'followers_count'. Normalize so the real follower count reaches the
        # model — a key mismatch historically rendered as 0 and the model
        # hallucinated a "metric contradiction" around it.
        profile_data = {
            **profile_data,
            "followers_count": profile_data.get("followers_count") or profile_data.get("follower_count"),
        }
        # following/posts are never exposed by some providers (e.g. ScrapeCreators
        # Facebook) — they arrive as 0 placeholders. Presenting them as real zeros
        # makes the model invent narratives ("purchased followers", "metric
        # contradictions"), so render them as unknown instead.
        def _metric(key, raw=None):
            val = raw if raw is not None else profile_data.get(key)
            return f"{val:,}" if val else "unknown (not exposed by provider)"

        # Nothing fetched (provider returned no profile metrics AND no content):
        # any risk verdict would be a guess dressed as a measurement. Say so.
        _no_metrics = not any(profile_data.get(k) for k in (
            "followers_count", "following_count", "posts_count", "bio", "profile_image_url"))
        if content_items is None:
            _no_content = not (content_analysis.get("key_insights") or content_analysis.get("content_themes"))
        else:
            _no_content = len(content_items) == 0
        if _no_metrics and _no_content:
            return {
                "assessment": "insufficient_data",
                "risk_assessment": "unknown",
                "bot_likelihood": None,
                "overall_authenticity": {"score": None, "confidence": 0.0},
                "fake_follower_risk": None,
                "content_authenticity": None,
                "red_flags": [],
                "green_flags": [],
                "limitations": [
                    "No profile metrics, bio, image or content were returned by the provider for this account.",
                    "Authenticity cannot be assessed without data; no verdict is being reported.",
                ],
            }

        # What the samples actually contain decides both what the prompt may
        # permit and which indicators survive validation below.
        avail = _content_availability(content_items, profile_data)
        boundaries = _boundary_text(avail)

        profile_metrics = f"""
Username: @{profile_data.get('username')}
Account Age: {profile_data.get('created_at', 'Unknown')}
Followers: {_metric('followers_count')}
Following: {_metric('following_count')}
Posts: {_metric('posts_count')}
Verified: {profile_data.get('verified', False)}
Bio Length: {len(profile_data.get('bio') or '')} characters
Profile Image: {'Present' if profile_data.get('profile_image_url') else 'Missing'}
        """.strip()
        
        content_summary = json.dumps(content_analysis.get('key_insights', []), indent=2)

        # Verbatim post text: the model may describe the account's topical focus
        # only by quoting from here, and those quotes are checked afterwards.
        samples = []
        for item in (content_items or [])[:15]:
            if isinstance(item, dict):
                body = str(item.get("text") or item.get("content") or "").strip()
                if body:
                    samples.append(f"- {body[:300]}")
        verbatim_samples = "\n".join(samples) or "(no post text was collected)"
        
        messages = [
            {
                "role": "system",
                "content": f"""You are a cybersecurity expert specializing in fake account detection and 
                social media authenticity analysis. Analyze profiles for signs of automation, bot behavior, 
                purchased followers, and other authenticity issues.
                CRITICAL: If 'Verified' is True, start with a high base trust score (>0.8) unless you find specific evidence of compromise (hacked verified account).
                CRITICAL: Any metric marked 'unknown (not exposed by provider)' is MISSING data, not zero.
                Never treat an unknown metric as evidence (e.g. do not infer purchased followers from an
                unknown following count).
                Every red/green flag must be traceable to a number or a sample in the data below;
                indicators that reference a dimension marked unavailable will be discarded.

                {boundaries}"""
            },
            {
                "role": "user",
                "content": f"""Analyze this profile for authenticity:

PROFILE METRICS:
{profile_metrics}

DATASET:
{boundaries}

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
10. topical_focus: Object describing what this account actually talks about:
    - primary_topic: 3-8 word label (e.g. "regional politics and civic commentary")
    - political_intensity: 0-1, the share of samples that are political or civic
    - evidence: 2-3 snippets copied VERBATIM from COLLECTED POSTS below (no paraphrase, no translation)
    Topic is a property of the posts, NOT a trust signal: never turn a topical niche
    (political or otherwise) into a red flag, a green flag, or a risk level by itself.
    If the samples are too thin to characterise the topic, use "Unknown" and no evidence.

COLLECTED POSTS (verbatim, for topical_focus evidence only):
{verbatim_samples}

Be thorough in detecting fake accounts, bot networks, and purchased engagement - 
but only on evidence the DATASET section says was collected."""
            }
        ]
        
        try:
            result = self._request_json(
                messages,
                model=self.default_models["authenticity_analysis"],
                temperature=0.2,
                max_tokens=3000,
                label="authenticity",
            )
            grounded = _apply_flag_grounding(result, avail)
            return _validate_topical_focus(grounded, content_items)

        except (json.JSONDecodeError, ValueError) as e:
            # A 0.5 "default score" here read as a measurement. There is no
            # verdict when the analysis did not complete, so say exactly that.
            logger.warning(f"Authenticity analysis unavailable: {e}")
            return {
                "assessment": "analysis_unavailable",
                "risk_assessment": "unknown",
                "bot_likelihood": None,
                "overall_authenticity": {"score": None, "confidence": 0.0},
                "red_flags": [],
                "green_flags": [],
                "error": "Authenticity analysis could not be generated in this run",
                "limitations": [
                    "The authenticity analysis did not produce usable output; no verdict is being reported.",
                ],
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
        
        # Route through analyze(): it retries empty completions and re-requests
        # once at double budget when the JSON looks truncated. The old direct
        # parse() fell back to a zeroed forecast, which read as data ("0 growth")
        # when in fact nothing had been produced.
        result = self.analyze(
            prompt=messages[1]["content"],
            system_prompt=messages[0]["content"],
            model_type="trend_analysis",
            max_tokens=4000,
        )
        if isinstance(result, dict) and result.get("error"):
            logger.warning("Predictions unavailable: %s", result.get("error"))
            return {
                "growth_forecast": {"30_day": None, "90_day": None, "365_day": None},
                "error": "Predictions could not be generated in this run",
                "limitations": ["Prediction output was not produced; no forecast is being reported."],
            }
        return result
    
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