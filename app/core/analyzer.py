"""
Vanta: Core Analyzer Module
Main orchestrator for social media profile analysis
"""

import json
import os
from contextlib import contextmanager
from typing import Dict, Any, Optional
from datetime import datetime

from .data_collector import DataCollector
from .content_analyzer import ContentAnalyzer
from .authenticity import ProfileAuthenticityAnalyzer
from .prediction import PredictionEngine
from .openrouter_client import openrouter_client, OpenRouterError
from ..utils.logger import setup_logger


# Shared app for cache access outside a request/worker context, created at most
# once per process. None means it could not be created (no database configured),
# in which case caching is skipped and runs behave as before.
_CACHE_APP = None
_CACHE_APP_FAILED = False


def _shared_cache_app():
    global _CACHE_APP, _CACHE_APP_FAILED
    if _CACHE_APP is not None or _CACHE_APP_FAILED:
        return _CACHE_APP
    try:
        from app.web.app import create_app
        _CACHE_APP = create_app()
    except Exception:
        _CACHE_APP_FAILED = True
    return _CACHE_APP


class CollectionEmptyError(RuntimeError):
    """Collection produced no subject to analyse.

    Raised instead of proceeding, because a report generated from an empty
    dossier is not a weak report: it is a report about nobody, whose empty
    sections and failed summary read like findings about the account.
    """


class SocialMediaAnalyzer:
    """Main application for social media profile analysis"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the analyzer with optional configuration
        Args:
            config_path: Path to configuration file
        """
        self.config = self._load_config(config_path)
        self.logger = setup_logger("Vanta.Analyzer", self.config["logging"])

        # Collectors are now initialized dynamically per platform
        self._collector_cache = {}

        self.content_analyzer = ContentAnalyzer(
            nlp_model=self.config["analysis"]["nlp_model"],
            sentiment_analyzer=self.config["analysis"]["sentiment_analysis"],
        )

        self.authenticity_analyzer = ProfileAuthenticityAnalyzer()

        threshold = self.config["analysis"]["confidence_threshold"]
        self.prediction_engine = PredictionEngine(confidence_threshold=threshold)

    @staticmethod
    def _sentiment_section(core_intel: Dict[str, Any], dossier_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sentiment split for the collected posts.

        A model-supplied distribution wins. Otherwise the posts themselves are
        scored with the VADER lexicon in nlp_utils: a 41-post profile used to be
        reported as 100% neutral from a hardcoded default, which the report read
        as a finding about a plainly upbeat account. With nothing collected there
        is no split to show, and coverage marks the section not measured.
        """
        given = ((core_intel or {}).get("general_analysis") or {}).get("sentiment")
        if isinstance(given, dict) and {"positive", "neutral", "negative"} <= set(given):
            return given

        posts = [p for p in (dossier_data.get("content") or []) if isinstance(p, dict)]
        texts = [str(p.get("text") or p.get("content") or "").strip() for p in posts]
        texts = [t for t in texts if t]
        if not texts:
            return {"overall": "unknown", "positive": 0, "neutral": 0, "negative": 0}

        from ..utils.nlp_utils import analyze_sentiment

        counts = {"positive": 0, "neutral": 0, "negative": 0}
        for text in texts:
            compound = analyze_sentiment(text).get("compound", 0.0)
            label = "positive" if compound >= 0.05 else "negative" if compound <= -0.05 else "neutral"
            counts[label] += 1

        total = len(texts)
        percentages = {name: round(count * 100 / total) for name, count in counts.items()}
        return {"overall": max(percentages, key=percentages.get), **percentages}

    def _get_collector(self, platform: str) -> DataCollector:
        """Get or create a collector for the specified platform.

        The cache key includes a fingerprint of the resolved BYOK keys so
        a collector built for one user's keys is never reused for another.
        """
        platform = platform.lower()
        from hashlib import sha256
        from app.utils.config import resolve_api_key
        keys_fp = sha256(
            ((resolve_api_key("SCRAPECREATORS_API_KEY") or "")
             + "|" + (resolve_api_key("APIFY_API_TOKEN") or "")
             + "|" + (resolve_api_key("OPENROUTER_API_KEY") or "")).encode()
        ).hexdigest()[:12]
        cache_key = f"{platform}:{keys_fp}"
        if cache_key not in self._collector_cache:
            # Get specific rate limit if configured, otherwise use default
            rate_limit = self.config["rate_limits"].get(platform, 60)
            self._collector_cache[cache_key] = DataCollector(platform, rate_limit)
        return self._collector_cache[cache_key]

    # ------------------------------------------------------------------
    # Dossier cache: re-analysis must not re-scrape data that has not changed.
    # A web or Celery run is scoped to its signed-in user. A CLI or desktop run
    # has no signed-in user but is still one operator on one machine, so it
    # uses an operator-local scope instead of opting out of the cache - which is
    # why a desktop re-run of the same handle used to spend the credits the
    # cache exists to save.
    # ------------------------------------------------------------------
    @staticmethod
    @contextmanager
    def _cache_scope():
        """Yield (session, owner_id, ttl_hours), or None when unavailable.

        Outside a Flask app context (CLI, desktop, scripts) a shared app is
        created once so the local database - the same `data/vanta.db` the local
        web UI uses - can serve the cache.
        """
        try:
            ttl = int(os.getenv("DOSSIER_CACHE_TTL_HOURS", "12") or "12")
        except ValueError:
            ttl = 12

        try:
            from app.web.models.dossier import LOCAL_CACHE_OWNER
            from app.utils.config import get_user_context
            from flask import has_app_context
        except Exception:
            yield None
            return

        owner = LOCAL_CACHE_OWNER
        user_id = (get_user_context() or {}).get("user_id")
        if user_id:
            owner = int(user_id)

        if has_app_context():
            try:
                from app.web.models import db
                yield db.session, owner, ttl
            except Exception:
                yield None
            return

        app = _shared_cache_app()
        if app is None:
            yield None
            return
        with app.app_context():
            from app.web.models import db
            yield db.session, owner, ttl

    def _cache_lookup(self, platform: str, profile_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._cache_scope() as scope:
                if scope is None:
                    return None
                session, owner, _ttl = scope
                from app.web.models.dossier import get_cached_dossier
                return get_cached_dossier(session, owner, platform, profile_id)
        except Exception as exc:
            self.logger.warning(f"Dossier cache lookup failed (collecting instead): {exc}")
            return None

    def _cache_store(self, platform: str, profile_id: str, dossier: Dict[str, Any]) -> None:
        try:
            with self._cache_scope() as scope:
                if scope is None:
                    return
                session, owner, ttl = scope
                from app.web.models.dossier import store_cached_dossier
                payload = {k: v for k, v in dossier.items() if k != "source"}
                store_cached_dossier(session, owner, platform, profile_id, payload,
                                     ttl_hours=ttl)
        except Exception as exc:
            # A cache write must never fail a run that already collected data.
            self.logger.warning(f"Dossier cache write failed: {exc}")

    # A profile dict carrying any of these describes a real subject; none of
    # them and no posts means the run has nothing to describe at all.
    _SUBJECT_FIELDS = ("username", "display_name", "follower_count", "posts_count",
                       "like_count", "profile_image_url")

    @classmethod
    def _require_something_to_analyse(cls, platform: str, profile_id: str,
                                      dossier_data: Dict[str, Any]) -> None:
        """Refuse to report on a dossier that carries no subject.

        Empty sections plus a failed executive summary are not a neutral
        result: they read as findings about an account. A private profile, a
        deleted one and a provider outage all arrive this way, so the run ends
        with the reason it collected instead of a report about nobody.
        """
        dossier_data = dossier_data or {}
        profile = dossier_data.get("profile") or {}
        has_subject = isinstance(profile, dict) and any(
            profile.get(field) for field in cls._SUBJECT_FIELDS
        )
        if has_subject or dossier_data.get("content"):
            return

        unavailable = dossier_data.get("unavailable") or {}
        errors = [str(err).strip() for err in (dossier_data.get("errors") or [])
                  if str(err).strip()]
        if unavailable.get("message"):
            reason = f"{platform}/{profile_id} cannot be analysed: {unavailable['message']}"
        elif errors:
            reason = f"{platform}/{profile_id} collection failed: {errors[0]}"
        else:
            reason = f"{platform}/{profile_id} returned no profile data and no posts"
        raise CollectionEmptyError(
            reason + ". No report was generated and nothing was filled in to replace it."
        )

    @staticmethod
    def _build_coverage(results: Dict[str, Any], dossier: Dict[str, Any]) -> Dict[str, Any]:
        """State, per tab, what was measured and what was missing.

        Deterministic and computed from the dossier, so every section carries a
        receipt about its own inputs instead of asking a model to police itself.
        A section with no underlying data is reported as such rather than shown
        as a finding.
        """
        from .platform_prompts import _content_availability

        profile = (dossier or {}).get("profile") or {}
        content = (dossier or {}).get("content") or []
        stats = (dossier or {}).get("statistics") or {}
        avail = _content_availability(content, profile)

        metric_gaps = [
            label for label, present in (
                ("account age", profile.get("created_at")),
                ("following count", profile.get("following_count")),
                ("post count", profile.get("posts_count")),
                ("follower/following lists", avail["has_network"]),
                ("group membership", avail["has_groups"]),
            ) if not present
        ]

        def section(name: str, payload: Any, basis: str, measured: bool) -> Dict[str, Any]:
            return {
                "section": name,
                "basis": basis,
                "status": "measured" if measured else "not_measured",
            }

        from ..utils.nlp_utils import sentiment_backend

        scorer = "the VADER lexicon" if sentiment_backend() == "vader" else "an offline word list"

        items = [
            section("sentiment", results.get("sentiment"),
                    f"{avail['n_items']} collected posts, scored with {scorer}",
                    avail["n_items"] > 0),
            section("content", results.get("content_analysis"),
                    f"{avail['n_items']} posts, {avail['engagement_items']} with engagement metrics",
                    avail["n_items"] > 0),
            section("authenticity", results.get("authenticity"),
                    f"profile metrics + {avail['n_items']} posts",
                    bool(profile) or avail["n_items"] > 0),
            section("beliefs", results.get("belief_system"),
                    f"post text from {avail['n_items']} items", avail["n_items"] > 0),
            section("psychology", results.get("content_analysis"),
                    f"writing samples from {avail['n_items']} items", avail["n_items"] > 0),
            section("consumer", results.get("consumer_profile"),
                    f"brand/product mentions in {avail['n_items']} posts",
                    avail["n_items"] > 0),
            section("lifestyle", results.get("behavioral_profile"),
                    f"{avail['n_items']} posts + {stats.get('comments_collected', 0)} comments",
                    avail["n_items"] > 0),
            section("network", None,
                    "follower/following samples", avail["has_network"]),
        ]

        # Collection failures are part of the receipt: without them a run that
        # collected nothing reads like an account with nothing to say.
        collection_errors = [
            str(err) for err in ((dossier or {}).get("errors") or []) if str(err).strip()
        ]

        return {
            "measured": [i for i in items if i["status"] == "measured"],
            "not_measured": [i for i in items if i["status"] != "measured"],
            "missing_inputs": metric_gaps,
            "collection_errors": collection_errors,
            # Where this run's inputs came from: a fresh scrape or the cache.
            "dossier_source": (dossier or {}).get("source"),
            "dossier_collected_at": (dossier or {}).get("collected_at"),
            "counts": {
                "posts": avail["n_items"],
                "posts_with_engagement": avail["engagement_items"],
                "comments": stats.get("comments_collected"),
                "gendered_commenters": avail["gendered_commenters"],
            },
        }

    # Each collection stage owns a slice of the bar. The percentage moves only
    # when a real step completes, so a run that stalls on one feed holds still
    # instead of creeping toward a finish it has not reached.
    _STAGE_BANDS = {
        "profile": (10, 14),
        "feeds": (14, 48),
        "comments": (48, 62),
        "transcripts": (62, 68),
        "enrichment": (68, 72),
        "collected": (72, 74),
    }

    @staticmethod
    def _stage_percent(stage: str, done, total) -> Optional[int]:
        band = SocialMediaAnalyzer._STAGE_BANDS.get(stage)
        if band is None:
            return None
        start, end = band
        if not total:
            return start
        fraction = min(max(float(done or 0) / float(total), 0.0), 1.0)
        return int(round(start + (end - start) * fraction))

    def analyze_profile(self, platform: str, profile_id: str, mode: str = "deep",
                        progress=None) -> Dict[str, Any]:
        """
        Perform complete analysis of a social media profile using Enhanced Engines (Phase 2 & 3)
        Args:
            platform: Social platform name
            profile_id: Username or ID
            mode: 'quick' (10s) or 'deep' (2-5m)
        Returns:
            Complete analysis results
        """
        self.logger.info(f"Starting {mode.upper()} analysis of {profile_id} on {platform}")

        last_reported = {"message": None}

        def report(message: str, percent: Optional[int] = None) -> None:
            """Report what is happening now; repeats are dropped."""
            if progress is None or message == last_reported["message"]:
                return
            last_reported["message"] = message
            try:
                progress(message, percent)
            except Exception as exc:  # pragma: no cover - defensive
                self.logger.warning(f"Progress reporting failed: {exc}")

        def on_stage(stage: str, note: str, done=None, total=None) -> None:
            report(note, self._stage_percent(stage, done, total))

        try:
            # ═══════════════════════════════════════════════════════════════
            # PHASE 2: DATA COLLECTION (cache-aware)
            # ═══════════════════════════════════════════════════════════════
            cache = self._cache_lookup(platform, profile_id)
            if cache is not None:
                dossier_data = dict(cache)
                dossier_data['source'] = 'cache'
                self.logger.info(
                    f"Reusing cached dossier for {platform}/{profile_id} "
                    f"(collected {dossier_data.get('collected_at')}); 0 credits spent"
                )
                report(
                    f"reusing the dossier collected {str(dossier_data.get('collected_at'))[:16]} "
                    f"(no provider credits spent)",
                    self._stage_percent("collected", None, None),
                )
            else:
                from .deep_collector import create_deep_collector

                # Use the new Deep Dossier Collector
                collector = create_deep_collector()

                if mode == 'quick':
                    # Quick Scan: 10 seconds, limited data
                    report("collecting the profile and 10 recent posts",
                           self._stage_percent("profile", None, None))
                    dossier_data = collector.quick_scan(platform, profile_id)
                else:
                    # Deep Dossier: 2-5 mins, full data
                    dossier_data = collector.deep_dossier(
                        platform=platform,
                        username=profile_id,
                        include_comments=True,
                        include_transcripts=True,
                        on_stage=on_stage,
                    )
                dossier_data['source'] = 'live'
                # Only a run that actually collected something may seed the cache;
                # caching an empty dossier would serve emptiness for the whole TTL.
                if dossier_data.get('profile') or dossier_data.get('content'):
                    self._cache_store(platform, profile_id, dossier_data)

            # ═══════════════════════════════════════════════════════════════
            self.logger.info(f"Dossier Data Keys: {list(dossier_data.keys())}")
            self.logger.info(f"Profile Data collected: {dossier_data.get('profile', {})}")

            # A private/deleted profile and a provider outage both arrive as an
            # empty dossier. Neither is a subject with nothing to say, so the
            # run ends with the real reason instead of an analysis of nothing.
            self._require_something_to_analyse(platform, profile_id, dossier_data)

            # ═══════════════════════════════════════════════════════════════
            # PHASE 3: MASTER INTELLIGENCE ANALYSIS
            # ═══════════════════════════════════════════════════════════════
            from .intelligence_analyzer import create_intelligence_analyzer
            
            # Use the new Master Intelligence Analyzer
            intelligence_engine = create_intelligence_analyzer()
            
            # Generate the full comprehensive report. One LLM pass, so the bar
            # has nothing honest to say until it returns.
            posts = len(dossier_data.get('content') or [])
            comments = ((dossier_data.get('comments_analysis') or {})
                        .get('total_comments_collected') or 0)
            report(
                f"writing the report from {posts} posts and {comments} comments "
                f"(one model pass, no partial output)",
                76,
            )
            full_report = intelligence_engine.generate_full_report(dossier_data)
            report("report written; assembling sections and coverage", 92)
            
            # ═══════════════════════════════════════════════════════════════
            # MAP TO FRONTEND SCHEMA
            # ═══════════════════════════════════════════════════════════════
            
            core_intel = full_report.get("core_intelligence", {})
            profile_data = dossier_data.get("profile", {}) or {}
            
            results = {
                "profile_info": {
                    "username": profile_data.get("username", profile_id),
                    "followers": profile_data.get("follower_count", profile_data.get("followers_count", 0)) or 0,
                    "following": profile_data.get("following_count", 0) or 0,
                    "posts": profile_data.get("posts_count", 0) or 0,
                    "like_count": profile_data.get("like_count"),
                    "talking_about_count": profile_data.get("talking_about_count"),
                    "category": profile_data.get("category"),
                    "display_name": profile_data.get("display_name"),
                    "bio": profile_data.get("bio"),
                    "profile_image_url": profile_data.get("profile_image_url") or profile_data.get("avatar_url"),
                    "is_verified": profile_data.get("verified"),
                    "location": profile_data.get("location"),
                    "website": profile_data.get("website")
                },
                "connected_accounts": dossier_data.get("connected_accounts", []),
                "sentiment": self._sentiment_section(core_intel, dossier_data),
                "content_analysis": core_intel.get("general_analysis", {}),
                "authenticity": core_intel.get("authenticity", {}),
                "predictions": core_intel.get("predictions", {}),
                # New Vanta Intelligence Sections
                "belief_system": full_report.get("belief_system", {}),
                "consumer_profile": full_report.get("consumer_profile", {}),
                "behavioral_profile": full_report.get("behavioral_profile", {}),
                "executive_summary": full_report.get("executive_summary", ""),
                
                "metadata": {
                    "profile_id": profile_id,
                    "platform": platform,
                    "analysis_date": datetime.now().isoformat(),
                    "analyzer_version": "2.0.0 (Vanta Deep Intelligence)",
                    "collection_mode": mode.lower(),
                    "dossier_source": dossier_data.get("source"),
                },
                
                # Debug data
                "raw_stats": dossier_data.get("statistics", {})
            }

            # Save raw data if configured
            if self.config["output"]["save_raw_data"]:
                results["raw_dossier"] = dossier_data

            results["data_coverage"] = self._build_coverage(results, dossier_data)

            self.logger.info(f"Analysis completed for {profile_id}")
            return results
        except Exception as e:
            self.logger.error(
                f"Error analyzing profile {profile_id} on {platform}: {str(e)}",
                exc_info=True,
            )
            raise

    def export_results(self, results: Dict[str, Any], output_path: str) -> None:
        """
        Export analysis results to file
        Args:
            results: Analysis results to export
            output_path: Path to save results
        """
        format_type = self.config["output"]["export_format"].lower()
        self.logger.info(f"Exporting results to {output_path} in {format_type} format")

        if format_type == "json":
            with open(output_path, "w") as f:
                json.dump(results, f, indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")

        self.logger.info(f"Results exported to {output_path}")

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration from file or use defaults"""
        default_config = {
            "rate_limits": {"twitter": 100, "facebook": 100},
            "analysis": {
                "nlp_model": "default",
                "sentiment_analysis": True,
                "confidence_threshold": 0.65,
            },
            "output": {"save_raw_data": True, "export_format": "json"},
            "logging": {"level": "INFO", "file": "logs/vanta.log"},
        }

        if not config_path:
            return default_config

        try:
            with open(config_path, "r") as f:
                config = json.load(f)

            # Merge with defaults for any missing values
            merged_config = default_config.copy()
            for section, values in config.items():
                if section in merged_config:
                    if isinstance(merged_config[section], dict):
                        merged_config[section].update(values)
                    else:
                        merged_config[section] = values
                else:
                    merged_config[section] = values

            return merged_config
        except Exception as e:
            print(f"Error loading config: {e}")
            return default_config
