"""
Vanta: Core Analyzer Module
Main orchestrator for social media profile analysis
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime

from .data_collector import DataCollector
from .content_analyzer import ContentAnalyzer
from .authenticity import ProfileAuthenticityAnalyzer
from .prediction import PredictionEngine
from .openrouter_client import openrouter_client, OpenRouterError
from ..utils.logger import setup_logger


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

        items = [
            section("sentiment", results.get("sentiment"),
                    f"{avail['n_items']} collected posts", avail["n_items"] > 0),
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
            "counts": {
                "posts": avail["n_items"],
                "posts_with_engagement": avail["engagement_items"],
                "comments": stats.get("comments_collected"),
                "gendered_commenters": avail["gendered_commenters"],
            },
        }

    def analyze_profile(self, platform: str, profile_id: str, mode: str = "deep") -> Dict[str, Any]:
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

        try:
            # ═══════════════════════════════════════════════════════════════
            # PHASE 2: DATA COLLECTION
            # ═══════════════════════════════════════════════════════════════
            from .deep_collector import create_deep_collector
            
            # Use the new Deep Dossier Collector
            collector = create_deep_collector()
            
            if mode == 'quick':
                # Quick Scan: 10 seconds, limited data
                dossier_data = collector.quick_scan(platform, profile_id)
            else:
                # Deep Dossier: 2-5 mins, full data
                dossier_data = collector.deep_dossier(
                    platform=platform, 
                    username=profile_id,
                    include_comments=True,
                    include_transcripts=True
                )
            
            # ═══════════════════════════════════════════════════════════════
            self.logger.info(f"Dossier Data Keys: {list(dossier_data.keys())}")
            self.logger.info(f"Profile Data collected: {dossier_data.get('profile', {})}")

            # ═══════════════════════════════════════════════════════════════
            # PHASE 3: MASTER INTELLIGENCE ANALYSIS
            # ═══════════════════════════════════════════════════════════════
            from .intelligence_analyzer import create_intelligence_analyzer
            
            # Use the new Master Intelligence Analyzer
            intelligence_engine = create_intelligence_analyzer()
            
            # Generate the full comprehensive report
            full_report = intelligence_engine.generate_full_report(dossier_data)
            
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
                    "is_verified": profile_data.get("verified", False),
                    "location": profile_data.get("location"),
                    "website": profile_data.get("website")
                },
                "connected_accounts": dossier_data.get("connected_accounts", []),
                "sentiment": core_intel.get("general_analysis", {}).get("sentiment", {
                    "overall": "neutral",
                    "positive": 0, "neutral": 100, "negative": 0
                }),
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
