"""
Vanta: Data Collection Module
Handles collecting profile data from various social media platforms
"""

import os
import json
import logging
import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import requests
import time

# Optional imports for social media APIs
try:
    import tweepy
except ImportError:
    tweepy = None

try:
    from facebook_business.exceptions import FacebookRequestError
except ImportError:
    # Fallback for when facebook_business is not available
    class FacebookRequestError(Exception):
        pass

from ..utils.config import load_config, ConfigError
from .scrape_client import get_scrape_client, get_apify_client

# Setup module logger
logger = logging.getLogger("Vanta.DataCollector")


class DataCollectionError(Exception):
    """Base exception for data collection errors"""

    pass


class APIError(DataCollectionError):
    """Exception raised when an API request fails"""

    def __init__(self, message: str, platform: str, error_code: int = None):
        self.platform = platform
        self.error_code = error_code
        super().__init__(f"{platform.capitalize()} API error: {message}")


class RateLimitError(DataCollectionError):
    """Exception raised when API rate limit is exceeded"""

    def __init__(self, platform: str, reset_time: Optional[datetime] = None):
        self.platform = platform
        self.reset_time = reset_time
        message = f"{platform.capitalize()} API rate limit exceeded"
        if reset_time:
            message += f". Try again after {reset_time}"
        super().__init__(message)


class AuthenticationError(DataCollectionError):
    """Exception raised when authentication fails"""

    def __init__(self, message: str, platform: str):
        self.platform = platform
        super().__init__(f"{platform.capitalize()} authentication error: {message}")


class DataCollector:
    """Collects data from social media platforms using ScrapeCreators API."""

    def __init__(self, platform: str, rate_limit: int = 60, use_mock_data: bool = False):
        """
        Initialize data collector for a specific platform

        Args:
            platform: Social media platform name
            rate_limit: API rate limit per minute
            use_mock_data: If True, use mock data instead of API calls
        """
        self.platform = platform.lower()
        self.rate_limit = rate_limit
        self.last_request_time = 0
        self.use_mock_data = use_mock_data
        self.logger = logging.getLogger(f"Vanta.DataCollector.{platform}")
        self.error_messages = []

        # Data provider priority: Apify (if token set) -> ScrapeCreators -> mock.
        # Both are scrapers; OpenRouter (LLM) is separate and downstream.
        self.apify_client = get_apify_client()
        self.data_provider = "apify" if self.apify_client.is_configured else "scrapecreators"
        try:
            self.scrape_client = get_scrape_client()
            # If we got a mock client and didn't explicitly ask for mock data
            # Check specifically for the internal MockScrapeCreatorsClient, not just any "Mock" (like from unittest)
            if hasattr(self.scrape_client, "__class__") and "MockScrapeCreatorsClient" == self.scrape_client.__class__.__name__:
                if not self.use_mock_data:
                    self.logger.warning(f"ScrapeCreators API key missing. Using mock data for {self.platform}.")
                    self.use_mock_data = True
        except Exception as e:
            self.logger.error(f"Failed to initialize ScrapeCreators client: {e}")
            self.use_mock_data = True

    def collect_profile_data(self, profile_id: str) -> Dict[str, Any]:
        """
        Collect complete profile data from the platform via ScrapeCreators

        Args:
            profile_id: Username or ID of the profile to analyze

        Returns:
            Dictionary containing profile data
        """
        self._respect_rate_limit()
        self.logger.info(f"Collecting {self.platform} data for {profile_id}")

        if self.use_mock_data:
            return self._generate_mock_profile(profile_id)

        # Apify path: run actor, normalize first item as profile
        if self.data_provider == "apify":
            try:
                apify_data = self.apify_client.scrape_profile(self.platform, profile_id)
                items = apify_data.get("items") or []
                data = items[0] if items and isinstance(items[0], dict) else {"items": items}
                if not isinstance(data, dict):
                    data = {"items": items}
                data.setdefault("platform", self.platform)
                data.setdefault("username", profile_id)
                data["posts"] = items[1:] if len(items) > 1 else []
                data["deep_analysis"] = {}
                data["metadata"] = {"platform": self.platform, "collection_date": datetime.utcnow().isoformat() + "Z", "is_real_data": True, "provider": "apify", "actor": apify_data.get("actor")}
                return data
            except Exception as e:
                self.logger.warning(f"Apify failed for {self.platform}/{profile_id}: {e}; falling back to ScrapeCreators")
        try:
            # Dynamically call the correct method on the universal client
            method_name = f"get_{self.platform}_profile"
            if not hasattr(self.scrape_client, method_name):
                raise ValueError(f"Platform '{self.platform}' is not supported by the collector.")
            
            fetcher = getattr(self.scrape_client, method_name)
            data = fetcher(profile_id)
            
            # Attach posts
            # Attach posts and deep analysis data
            posts, deep_data = self.collect_posts(profile_id, count=20)
            data["posts"] = posts
            data["deep_analysis"] = deep_data
            
            # Standardize metadata
            if "metadata" not in data:
                data["metadata"] = {}
            
            data["metadata"].update({
                "platform": self.platform,
                "collection_date": datetime.utcnow().isoformat() + "Z",
                "is_real_data": True
            })
            
            return data
            
        except Exception as e:
            self.logger.error(f"Failed to collect real data for {profile_id}: {e}")
            self.error_messages.append(str(e))
            return self._generate_mock_profile(profile_id)

    def collect_posts(self, profile_id: str, count: int = 20) -> List[Dict[str, Any]]:
        """
        Collect recent posts from a profile

        Args:
            profile_id: Username or ID of the profile
            count: Number of posts to collect

        Returns:
            List of post data dictionaries
        """
        if self.use_mock_data:
            return self._generate_mock_posts(profile_id, count)

        try:
            # Deep Profiling: Platform-specific Data Collection
            deep_data = {}
            posts = []

            # TikTok Deep Dive
            if self.platform == "tiktok":
                videos = getattr(self.scrape_client, "get_tiktok_videos", lambda x, y: [])(profile_id, count=10)
                posts = videos # Use videos as posts
                # Try to get comments for the top video if available
                if videos and "video_id" in videos[0]:
                    comments = getattr(self.scrape_client, "get_tiktok_comments", lambda x: [])(videos[0]["video_id"])
                    deep_data["latest_video_comments"] = comments

            # Instagram Deep Dive
            elif self.platform == "instagram":
                # Use deep posts endpoint if available, otherwise fall back to generic
                posts = getattr(self.scrape_client, "get_instagram_posts_deep", lambda x, y: [])(profile_id, count=10)
                if not posts: # Fallback
                     posts = getattr(self.scrape_client, "get_instagram_posts", lambda x, y: [])(profile_id, count=10)

            # YouTube Deep Dive
            elif self.platform == "youtube":
                # Channel ID is often the profile_id for YouTube scrapes
                videos = getattr(self.scrape_client, "get_youtube_videos_deep", lambda x, y: [])(profile_id, count=5)
                posts = videos
                # Try to get transcript for latest video
                if videos and "video_id" in videos[0]:
                    transcript = getattr(self.scrape_client, "get_youtube_transcript", lambda x: "")(videos[0]["video_id"])
                    deep_data["latest_video_transcript"] = transcript

            # Facebook Deep (profile + paginated posts + reels + photos + comments)
            elif self.platform == "facebook":
                deep = self.scrape_client.collect_facebook_deep(profile_id)
                posts = deep.get("posts") or []
                deep_data["facebook_reels"] = deep.get("reels") or []
                deep_data["facebook_photos"] = deep.get("photos") or []
                deep_data["facebook_events"] = deep.get("events") or []
                deep_data["facebook_comments"] = deep.get("comments") or []
                deep_data["facebook_collection_errors"] = deep.get("errors") or []

            # Twitter/X Standard
            elif self.platform == "twitter":
                posts = self.scrape_client.get_twitter_posts(profile_id, count=20)
            
            # Default for others
            else:
                posts = []

            return posts, deep_data
        except Exception as e:
            self.logger.warning(f"Could not fetch deep data for {profile_id}: {e}")
            return [], {}

    def _respect_rate_limit(self) -> None:
        """Ensure we don't exceed the platform's API rate limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        # If we're making requests too quickly, pause
        if time_since_last < (60 / self.rate_limit):
            sleep_time = (60 / self.rate_limit) - time_since_last
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _generate_mock_profile(self, profile_id: str) -> Dict[str, Any]:
        """Generate a universal mock profile for any platform"""
        self.logger.info(f"Generating mock {self.platform} data for {profile_id}")
        
        return {
            "user_id": profile_id,
            "username": profile_id,
            "display_name": f"Mock {profile_id.title()}",
            "bio": f"This is a placeholder {self.platform.title()} profile description for {profile_id}.",
            "follower_count": 1000 + random.randint(0, 5000),
            "following_count": 500 + random.randint(0, 200),
            "posts_count": 100 + random.randint(0, 1000),
            "verified": False,
            "created_at": "2020-01-01T00:00:00Z",
            "profile_image_url": f"https://example.com/assets/mock_{self.platform}.jpg",
            "posts": self._generate_mock_posts(profile_id, 10),
            "metadata": {
                "platform": self.platform,
                "collection_date": datetime.utcnow().isoformat() + "Z",
                "is_mock_data": True,
                "api_errors": self.error_messages if self.error_messages else None,
            },
        }

    def _generate_mock_posts(self, profile_id: str, count: int) -> List[Dict[str, Any]]:
        """Generate universal mock posts for any platform"""
        posts = []
        for i in range(min(count, 20)):
            posts.append({
                "post_id": f"{profile_id}_mock_post_{i}",
                "content": f"This is a sample {self.platform} post #{i} content for testing purposes.",
                "created_at": (datetime.utcnow() - timedelta(days=i)).isoformat() + "Z",
                "likes": i * random.randint(1, 10),
                "shares": i * random.randint(0, 5),
                "is_mock_data": True,
            })
        return posts
