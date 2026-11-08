"""
ScrapeCreators API Client for Social Media Data Collection
Universal social media scraping using ScrapeCreators API
"""

import os
import requests
import time
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class ScrapeCreatorsError(Exception):
    """ScrapeCreators API related errors"""
    pass

class RateLimitError(Exception):
    """Rate limit exceeded error"""
    pass

class ScrapeCreatorsClient:
    """Enhanced client for ScrapeCreators API"""
    
    def __init__(self):
        self.api_key = os.getenv("SCRAPECREATORS_API_KEY")
        self.base_url = os.getenv("SCRAPECREATORS_BASE_URL", "https://api.scrapecreators.com")
        
        if not self.api_key or self.api_key == "your_scrapecreators_api_key_here":
            logger.warning("ScrapeCreators API key not configured")
            self.api_key = None
            
        self.session = requests.Session()
        self.session.headers.update({
            "x-api-key": self.api_key,  # Correct header per ScrapeCreators docs
            "Content-Type": "application/json",
            "User-Agent": "Vanta/1.0"
        })
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between requests

    
    def _rate_limit(self):
        """Implement rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
            
        self.last_request_time = time.time()
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make API request with error handling"""
        if not self.api_key:
            raise ScrapeCreatorsError("API key not configured")
        
        self._rate_limit()
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            if response.status_code == 429:
                raise RateLimitError("Rate limit exceeded")
            elif response.status_code == 402:
                # Distinct marker so callers (DeepCollector) can fall back to Apify.
                # NOTE: do NOT match on 'credit' in body — successful 200s contain credits_remaining.
                raise ScrapeCreatorsError(f"CREDITS_EXHAUSTED: {response.status_code} - {response.text[:200]}")
            elif response.status_code == 401:
                raise ScrapeCreatorsError("Invalid API key")
            elif response.status_code == 404:
                raise ScrapeCreatorsError("Profile not found")
            elif response.status_code != 200:
                raise ScrapeCreatorsError(f"API error: {response.status_code} - {response.text}")
                
            return response.json()
            
        except requests.RequestException as e:
            raise ScrapeCreatorsError(f"Request failed: {str(e)}")
    
    def get_twitter_profile(self, username: str) -> Dict[str, Any]:
        """Get Twitter profile data"""
        # Correct endpoint per ScrapeCreators docs: /v1/twitter/profile?handle=xxx
        endpoint = "v1/twitter/profile"
        
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_twitter_data(response)
        except Exception as e:
            logger.error(f"Failed to get Twitter profile {username}: {e}")
            raise

    
    def get_instagram_profile(self, username: str) -> Dict[str, Any]:
        """Get Instagram profile data"""
        endpoint = "v1/instagram/profile"
        
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_instagram_data(response)
        except Exception as e:
            logger.error(f"Failed to get Instagram profile {username}: {e}")
            raise

    
    def get_linkedin_profile(self, username: str) -> Dict[str, Any]:
        """Get LinkedIn profile data"""
        endpoint = "v1/linkedin/profile"
        
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_linkedin_data(response)
        except Exception as e:
            logger.error(f"Failed to get LinkedIn profile {username}: {e}")
            raise

    
    def get_tiktok_profile(self, username: str) -> Dict[str, Any]:
        """Get TikTok profile data"""
        endpoint = "v1/tiktok/profile"
        
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_tiktok_data(response)
        except Exception as e:
            logger.error(f"Failed to get TikTok profile {username}: {e}")
            raise

    
    def get_youtube_profile(self, username: str) -> Dict[str, Any]:
        """Get YouTube profile data"""
        endpoint = "v1/youtube/profile"
        
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_youtube_data(response)
        except Exception as e:
            logger.error(f"Failed to get YouTube profile {username}: {e}")
            raise

    
    def get_snapchat_profile(self, username: str) -> Dict[str, Any]:
        """Get Snapchat profile data"""
        endpoint = "v1/snapchat/profile"
        
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_snapchat_data(response)
        except Exception as e:
            logger.error(f"Failed to get Snapchat profile {username}: {e}")
            raise

    
    def get_pinterest_profile(self, username: str) -> Dict[str, Any]:
        """Get Pinterest profile data"""
        endpoint = "v1/pinterest/profile"
        
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_pinterest_data(response)
        except Exception as e:
            logger.error(f"Failed to get Pinterest profile {username}: {e}")
            raise

    
    def get_reddit_profile(self, username: str) -> Dict[str, Any]:
        """Get Reddit profile data"""
        endpoint = "v1/reddit/profile"
        
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_reddit_data(response)
        except Exception as e:
            logger.error(f"Failed to get Reddit profile {username}: {e}")
            raise

    
    def get_github_profile(self, username: str) -> Dict[str, Any]:
        """Get GitHub profile data"""
        endpoint = "v1/github/profile"
        
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_github_data(response)
        except Exception as e:
            logger.error(f"Failed to get GitHub profile {username}: {e}")
            raise

    # --- NEW PLATFORMS (from ScrapeCreators docs) ---
    
    @staticmethod
    def _fb_url(username: str) -> str:
        """ScrapeCreators Facebook API needs a full URL param, not a handle.
        Accept a bare handle ('AzizMdArif'), '@AzizMdArif', or a full URL."""
        u = (username or "").strip()
        if u.startswith(("http://", "https://")):
            return u
        return f"https://www.facebook.com/{u.lstrip('@')}"

    def get_facebook_profile(self, username: str) -> Dict[str, Any]:
        """Get Facebook profile data (verified: param is `url`, not `handle`)"""
        endpoint = "v1/facebook/profile"
        try:
            response = self._make_request("GET", endpoint, params={"url": self._fb_url(username)})
            return self._normalize_generic_data(response, "facebook")
        except Exception as e:
            logger.error(f"Failed to get Facebook profile {username}: {e}")
            raise

    def get_threads_profile(self, username: str) -> Dict[str, Any]:
        """Get Threads profile data"""
        endpoint = "v1/threads/profile"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_generic_data(response, "threads")
        except Exception as e:
            logger.error(f"Failed to get Threads profile {username}: {e}")
            raise

    def get_bluesky_profile(self, username: str) -> Dict[str, Any]:
        """Get Bluesky profile data"""
        endpoint = "v1/bluesky/profile"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_generic_data(response, "bluesky")
        except Exception as e:
            logger.error(f"Failed to get Bluesky profile {username}: {e}")
            raise

    def get_twitch_profile(self, username: str) -> Dict[str, Any]:
        """Get Twitch profile data"""
        endpoint = "v1/twitch/profile"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_generic_data(response, "twitch")
        except Exception as e:
            logger.error(f"Failed to get Twitch profile {username}: {e}")
            raise

    def get_kick_profile(self, username: str) -> Dict[str, Any]:
        """Get Kick profile data"""
        endpoint = "v1/kick/profile"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_generic_data(response, "kick")
        except Exception as e:
            logger.error(f"Failed to get Kick profile {username}: {e}")
            raise

    def get_google_profile(self, username: str) -> Dict[str, Any]:
        """Get Google profile data"""
        endpoint = "v1/google/profile"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_generic_data(response, "google")
        except Exception as e:
            logger.error(f"Failed to get Google profile {username}: {e}")
            raise

    def get_linktree_profile(self, username: str) -> Dict[str, Any]:
        """Get Linktree profile data"""
        endpoint = "v1/linktree/profile"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_generic_data(response, "linktree")
        except Exception as e:
            logger.error(f"Failed to get Linktree profile {username}: {e}")
            raise

    def get_komi_profile(self, username: str) -> Dict[str, Any]:
        """Get Komi profile data"""
        endpoint = "v1/komi/profile"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_generic_data(response, "komi")
        except Exception as e:
            logger.error(f"Failed to get Komi profile {username}: {e}")
            raise

    def get_pillar_profile(self, username: str) -> Dict[str, Any]:
        """Get Pillar profile data"""
        endpoint = "v1/pillar/profile"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_generic_data(response, "pillar")
        except Exception as e:
            logger.error(f"Failed to get Pillar profile {username}: {e}")
            raise

    def get_linkbio_profile(self, username: str) -> Dict[str, Any]:
        """Get Linkbio profile data"""
        endpoint = "v1/linkbio/profile"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_generic_data(response, "linkbio")
        except Exception as e:
            logger.error(f"Failed to get Linkbio profile {username}: {e}")
            raise

    def get_tiktok_shop_profile(self, username: str) -> Dict[str, Any]:
        """Get TikTok Shop profile data"""
        endpoint = "v1/tiktok-shop/profile"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_generic_data(response, "tiktok_shop")
        except Exception as e:
            logger.error(f"Failed to get TikTok Shop profile {username}: {e}")
            raise

    def get_amazon_shop_profile(self, username: str) -> Dict[str, Any]:
        """Get Amazon Shop profile data"""
        endpoint = "v1/amazon-shop/profile"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return self._normalize_generic_data(response, "amazon_shop")
        except Exception as e:
            logger.error(f"Failed to get Amazon Shop profile {username}: {e}")
            raise

    # --- Ad Libraries ---
    def get_facebook_ad_library(self, advertiser: str) -> Dict[str, Any]:
        """Get Facebook Ad Library data for an advertiser"""
        endpoint = "v1/facebook-ad-library/ads"
        try:
            response = self._make_request("GET", endpoint, params={"advertiser": advertiser})
            return {"platform": "facebook_ad_library", "ads": response.get("ads", []), "raw": response}
        except Exception as e:
            logger.error(f"Failed to get Facebook Ad Library for {advertiser}: {e}")
            raise

    def get_google_ad_library(self, advertiser: str) -> Dict[str, Any]:
        """Get Google Ad Library data for an advertiser"""
        endpoint = "v1/google-ad-library/ads"
        try:
            response = self._make_request("GET", endpoint, params={"advertiser": advertiser})
            return {"platform": "google_ad_library", "ads": response.get("ads", []), "raw": response}
        except Exception as e:
            logger.error(f"Failed to get Google Ad Library for {advertiser}: {e}")
            raise

    def get_linkedin_ad_library(self, advertiser: str) -> Dict[str, Any]:
        """Get LinkedIn Ad Library data for an advertiser"""
        endpoint = "v1/linkedin-ad-library/ads"
        try:
            response = self._make_request("GET", endpoint, params={"advertiser": advertiser})
            return {"platform": "linkedin_ad_library", "ads": response.get("ads", []), "raw": response}
        except Exception as e:
            logger.error(f"Failed to get LinkedIn Ad Library for {advertiser}: {e}")
            raise

    # --- DEEP PROFILING ENDPOINTS (Enhanced Vanta Capabilities) ---

    def get_tiktok_videos(self, username: str, count: int = 10) -> List[Dict[str, Any]]:
        """Get TikTok videos for deep content analysis"""
        endpoint = "v1/tiktok/profile-videos"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username, "count": count})
            return response.get("videos", [])
        except Exception as e:
            logger.warning(f"Failed to get TikTok videos for {username}: {e}")
            return []

    def get_tiktok_comments(self, video_id: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get comments on a TikTok video for sentiment analysis"""
        endpoint = "v1/tiktok/comments"
        try:
            response = self._make_request("GET", endpoint, params={"video_id": video_id, "count": count})
            return response.get("comments", [])
        except Exception as e:
            logger.warning(f"Failed to get TikTok comments for {video_id}: {e}")
            return []

    # ═══════════════════════════════════════════════════════════════════════════
    # TIKTOK COMPLETE INTEGRATION - Vanta Deep Intelligence
    # ═══════════════════════════════════════════════════════════════════════════

    def get_tiktok_audience_demographics(self, username: str) -> Dict[str, Any]:
        """Get audience demographics for a TikTok user (age, gender, location breakdown)"""
        endpoint = "v1/tiktok/audience-demographics"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return {
                "age_distribution": response.get("age_distribution", {}),
                "gender_distribution": response.get("gender_distribution", {}),
                "top_countries": response.get("top_countries", []),
                "top_cities": response.get("top_cities", []),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get TikTok audience demographics for {username}: {e}")
            return {}

    def get_tiktok_video_info(self, video_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific TikTok video"""
        endpoint = "v1/tiktok/video-info"
        try:
            response = self._make_request("GET", endpoint, params={"video_id": video_id})
            return {
                "video_id": response.get("id"),
                "description": response.get("description", ""),
                "create_time": response.get("create_time"),
                "duration": response.get("duration"),
                "play_count": response.get("play_count", 0),
                "like_count": response.get("like_count", 0),
                "comment_count": response.get("comment_count", 0),
                "share_count": response.get("share_count", 0),
                "download_count": response.get("download_count", 0),
                "author": response.get("author", {}),
                "music": response.get("music", {}),
                "hashtags": response.get("hashtags", []),
                "mentions": response.get("mentions", []),
                "video_url": response.get("video_url"),
                "thumbnail_url": response.get("thumbnail_url"),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get TikTok video info for {video_id}: {e}")
            return {}

    def get_tiktok_transcript(self, video_id: str) -> Dict[str, Any]:
        """Get transcript/captions from a TikTok video for content analysis"""
        endpoint = "v1/tiktok/transcript"
        try:
            response = self._make_request("GET", endpoint, params={"video_id": video_id})
            return {
                "transcript": response.get("transcript", ""),
                "language": response.get("language", ""),
                "segments": response.get("segments", []),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get TikTok transcript for {video_id}: {e}")
            return {"transcript": "", "language": "", "segments": []}

    def get_tiktok_live(self, username: str) -> Dict[str, Any]:
        """Get live stream information for a TikTok user"""
        endpoint = "v1/tiktok/live"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return {
                "is_live": response.get("is_live", False),
                "room_id": response.get("room_id"),
                "title": response.get("title", ""),
                "viewer_count": response.get("viewer_count", 0),
                "start_time": response.get("start_time"),
                "thumbnail_url": response.get("thumbnail_url"),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get TikTok live info for {username}: {e}")
            return {"is_live": False}

    def get_tiktok_following(self, username: str, count: int = 50) -> List[Dict[str, Any]]:
        """Get list of accounts a TikTok user is following"""
        endpoint = "v1/tiktok/following"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username, "count": count})
            return response.get("following", response.get("users", []))
        except Exception as e:
            logger.warning(f"Failed to get TikTok following for {username}: {e}")
            return []

    def get_tiktok_followers(self, username: str, count: int = 50) -> List[Dict[str, Any]]:
        """Get list of accounts following a TikTok user"""
        endpoint = "v1/tiktok/followers"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username, "count": count})
            return response.get("followers", response.get("users", []))
        except Exception as e:
            logger.warning(f"Failed to get TikTok followers for {username}: {e}")
            return []

    def search_tiktok_users(self, query: str, count: int = 20) -> List[Dict[str, Any]]:
        """Search for TikTok users by keyword"""
        endpoint = "v1/tiktok/search-users"
        try:
            response = self._make_request("GET", endpoint, params={"query": query, "count": count})
            return response.get("users", [])
        except Exception as e:
            logger.warning(f"Failed to search TikTok users for '{query}': {e}")
            return []

    def search_tiktok_hashtag(self, hashtag: str, count: int = 20) -> Dict[str, Any]:
        """Search TikTok videos by hashtag"""
        endpoint = "v1/tiktok/search-hashtag"
        try:
            response = self._make_request("GET", endpoint, params={"hashtag": hashtag, "count": count})
            return {
                "hashtag_info": response.get("hashtag_info", {}),
                "videos": response.get("videos", []),
                "view_count": response.get("view_count", 0),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to search TikTok hashtag '{hashtag}': {e}")
            return {"videos": []}

    def search_tiktok_keyword(self, keyword: str, count: int = 20) -> Dict[str, Any]:
        """Search TikTok content by keyword"""
        endpoint = "v1/tiktok/search-keyword"
        try:
            response = self._make_request("GET", endpoint, params={"keyword": keyword, "count": count})
            return {
                "videos": response.get("videos", []),
                "users": response.get("users", []),
                "sounds": response.get("sounds", []),
                "hashtags": response.get("hashtags", []),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to search TikTok keyword '{keyword}': {e}")
            return {"videos": [], "users": [], "sounds": [], "hashtags": []}

    def get_tiktok_top_search(self) -> Dict[str, Any]:
        """Get top/trending search terms on TikTok"""
        endpoint = "v1/tiktok/top-search"
        try:
            response = self._make_request("GET", endpoint)
            return {
                "trending_searches": response.get("trending_searches", response.get("searches", [])),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get TikTok top searches: {e}")
            return {"trending_searches": []}

    def get_tiktok_popular_songs(self, count: int = 20) -> List[Dict[str, Any]]:
        """Get popular/trending songs on TikTok"""
        endpoint = "v1/tiktok/popular-songs"
        try:
            response = self._make_request("GET", endpoint, params={"count": count})
            return response.get("songs", response.get("music", []))
        except Exception as e:
            logger.warning(f"Failed to get TikTok popular songs: {e}")
            return []

    def get_tiktok_popular_creators(self, count: int = 20) -> List[Dict[str, Any]]:
        """Get popular/trending creators on TikTok"""
        endpoint = "v1/tiktok/popular-creators"
        try:
            response = self._make_request("GET", endpoint, params={"count": count})
            return response.get("creators", response.get("users", []))
        except Exception as e:
            logger.warning(f"Failed to get TikTok popular creators: {e}")
            return []

    def get_tiktok_popular_videos(self, count: int = 20) -> List[Dict[str, Any]]:
        """Get popular/trending videos on TikTok"""
        endpoint = "v1/tiktok/popular-videos"
        try:
            response = self._make_request("GET", endpoint, params={"count": count})
            return response.get("videos", [])
        except Exception as e:
            logger.warning(f"Failed to get TikTok popular videos: {e}")
            return []

    def get_tiktok_popular_hashtags(self, count: int = 20) -> List[Dict[str, Any]]:
        """Get popular/trending hashtags on TikTok"""
        endpoint = "v1/tiktok/popular-hashtags"
        try:
            response = self._make_request("GET", endpoint, params={"count": count})
            return response.get("hashtags", [])
        except Exception as e:
            logger.warning(f"Failed to get TikTok popular hashtags: {e}")
            return []

    def get_tiktok_song_details(self, song_id: str) -> Dict[str, Any]:
        """Get detailed information about a TikTok song/sound"""
        endpoint = "v1/tiktok/song-details"
        try:
            response = self._make_request("GET", endpoint, params={"song_id": song_id})
            return {
                "song_id": response.get("id"),
                "title": response.get("title", ""),
                "author": response.get("author", ""),
                "album": response.get("album", ""),
                "duration": response.get("duration"),
                "play_url": response.get("play_url"),
                "cover_url": response.get("cover_url"),
                "video_count": response.get("video_count", 0),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get TikTok song details for {song_id}: {e}")
            return {}

    def get_tiktoks_using_song(self, song_id: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get TikTok videos using a specific song/sound"""
        endpoint = "v1/tiktok/videos-by-song"
        try:
            response = self._make_request("GET", endpoint, params={"song_id": song_id, "count": count})
            return response.get("videos", [])
        except Exception as e:
            logger.warning(f"Failed to get TikToks using song {song_id}: {e}")
            return []

    def get_tiktok_trending_feed(self, count: int = 20) -> List[Dict[str, Any]]:
        """Get TikTok trending/For You feed content"""
        endpoint = "v1/tiktok/trending"
        try:
            response = self._make_request("GET", endpoint, params={"count": count})
            return response.get("videos", response.get("items", []))
        except Exception as e:
            logger.warning(f"Failed to get TikTok trending feed: {e}")
            return []

    # ═══════════════════════════════════════════════════════════════════════════
    # INSTAGRAM DEEP PROFILING
    # ═══════════════════════════════════════════════════════════════════════════

    def get_instagram_posts_deep(self, username: str, count: int = 12) -> List[Dict[str, Any]]:
        """Get detailed Instagram posts including captions"""
        endpoint = "v1/instagram/posts"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username, "count": count})
            return response.get("posts", [])
        except Exception as e:
            logger.warning(f"Failed to get Instagram posts for {username}: {e}")
            return []

    def get_instagram_basic_profile(self, username: str) -> Dict[str, Any]:
        """Get basic Instagram profile data (lighter than full profile)"""
        endpoint = "v1/instagram/basic-profile"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return response
        except Exception as e:
            logger.warning(f"Failed to get Instagram basic profile for {username}: {e}")
            return {}

    def get_instagram_post_info(self, post_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific Instagram post/reel"""
        endpoint = "v1/instagram/post-info"
        try:
            response = self._make_request("GET", endpoint, params={"post_id": post_id})
            return {
                "post_id": response.get("id"),
                "type": response.get("type", "post"),  # post, reel, carousel
                "caption": response.get("caption", ""),
                "like_count": response.get("like_count", 0),
                "comment_count": response.get("comment_count", 0),
                "view_count": response.get("view_count", 0),
                "play_count": response.get("play_count", 0),
                "timestamp": response.get("timestamp"),
                "location": response.get("location", {}),
                "hashtags": response.get("hashtags", []),
                "mentions": response.get("mentions", []),
                "media_url": response.get("media_url"),
                "thumbnail_url": response.get("thumbnail_url"),
                "author": response.get("author", {}),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get Instagram post info for {post_id}: {e}")
            return {}

    def get_instagram_transcript(self, reel_id: str) -> Dict[str, Any]:
        """Get transcript/captions from an Instagram reel"""
        endpoint = "v1/instagram/transcript"
        try:
            response = self._make_request("GET", endpoint, params={"reel_id": reel_id})
            return {
                "transcript": response.get("transcript", ""),
                "language": response.get("language", ""),
                "segments": response.get("segments", []),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get Instagram transcript for {reel_id}: {e}")
            return {"transcript": "", "language": "", "segments": []}

    def search_instagram_reels(self, query: str, count: int = 20) -> List[Dict[str, Any]]:
        """Search Instagram reels by keyword"""
        endpoint = "v1/instagram/search-reels"
        try:
            response = self._make_request("GET", endpoint, params={"query": query, "count": count})
            return response.get("reels", [])
        except Exception as e:
            logger.warning(f"Failed to search Instagram reels for '{query}': {e}")
            return []

    def get_instagram_comments(self, post_id: str, count: int = 50) -> List[Dict[str, Any]]:
        """Get comments on an Instagram post"""
        endpoint = "v1/instagram/comments"
        try:
            response = self._make_request("GET", endpoint, params={"post_id": post_id, "count": count})
            return response.get("comments", [])
        except Exception as e:
            logger.warning(f"Failed to get Instagram comments for {post_id}: {e}")
            return []

    def get_instagram_reels(self, username: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get Instagram reels for a user"""
        endpoint = "v1/instagram/reels"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username, "count": count})
            return response.get("reels", [])
        except Exception as e:
            logger.warning(f"Failed to get Instagram reels for {username}: {e}")
            return []

    def get_instagram_story_highlights(self, username: str) -> List[Dict[str, Any]]:
        """Get Instagram story highlights for a user"""
        endpoint = "v1/instagram/story-highlights"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return response.get("highlights", [])
        except Exception as e:
            logger.warning(f"Failed to get Instagram story highlights for {username}: {e}")
            return []

    def get_instagram_highlight_details(self, highlight_id: str) -> Dict[str, Any]:
        """Get detailed content of an Instagram story highlight"""
        endpoint = "v1/instagram/highlight-details"
        try:
            response = self._make_request("GET", endpoint, params={"highlight_id": highlight_id})
            return {
                "highlight_id": response.get("id"),
                "title": response.get("title", ""),
                "cover_url": response.get("cover_url"),
                "stories": response.get("stories", response.get("items", [])),
                "story_count": response.get("story_count", 0),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get Instagram highlight details for {highlight_id}: {e}")
            return {}

    def get_instagram_reels_using_song(self, song_id: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get Instagram reels using a specific song/audio"""
        endpoint = "v1/instagram/reels-by-song"
        try:
            response = self._make_request("GET", endpoint, params={"song_id": song_id, "count": count})
            return response.get("reels", [])
        except Exception as e:
            logger.warning(f"Failed to get Instagram reels using song {song_id}: {e}")
            return []

    def get_instagram_embed_html(self, post_url: str) -> Dict[str, Any]:
        """Get embed HTML for an Instagram post"""
        endpoint = "v1/instagram/embed"
        try:
            response = self._make_request("GET", endpoint, params={"url": post_url})
            return {
                "html": response.get("html", ""),
                "width": response.get("width"),
                "height": response.get("height"),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get Instagram embed HTML for {post_url}: {e}")
            return {"html": ""}

    # ═══════════════════════════════════════════════════════════════════════════
    # YOUTUBE COMPLETE INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════

    def get_youtube_channel_details(self, channel_id: str) -> Dict[str, Any]:
        """Get detailed YouTube channel information"""
        endpoint = "v1/youtube/channel-details"
        try:
            # FIX: API expects channelId (camelCase)
            response = self._make_request("GET", endpoint, params={"channelId": channel_id})
            return {
                "channel_id": response.get("id"),
                "title": response.get("title", ""),
                "description": response.get("description", ""),
                "custom_url": response.get("custom_url"),
                "subscriber_count": response.get("subscriber_count", 0),
                "video_count": response.get("video_count", 0),
                "view_count": response.get("view_count", 0),
                "country": response.get("country"),
                "published_at": response.get("published_at"),
                "thumbnail_url": response.get("thumbnail_url"),
                "banner_url": response.get("banner_url"),
                "keywords": response.get("keywords", []),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get YouTube channel details for {channel_id}: {e}")
            return {}

    def get_youtube_videos_deep(self, channel_id: str, count: int = 10) -> List[Dict[str, Any]]:
        """Get YouTube videos for the channel"""
        endpoint = "v1/youtube/channel-videos"
        try:
            # FIX: API expects channelId (camelCase)
            response = self._make_request("GET", endpoint, params={"channelId": channel_id, "count": count})
            return response.get("videos", [])
        except Exception as e:
            logger.warning(f"Failed to get YouTube videos for {channel_id}: {e}")
            return []

    def get_youtube_channel_shorts(self, channel_id: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get YouTube Shorts for the channel"""
        endpoint = "v1/youtube/channel-shorts"
        try:
            # FIX: API expects channelId (camelCase)
            response = self._make_request("GET", endpoint, params={"channelId": channel_id, "count": count})
            return response.get("shorts", [])
        except Exception as e:
            logger.warning(f"Failed to get YouTube shorts for {channel_id}: {e}")
            return []

    def get_youtube_video_details(self, video_id: str) -> Dict[str, Any]:
        """Get detailed information about a YouTube video"""
        endpoint = "v1/youtube/video-details"
        try:
            response = self._make_request("GET", endpoint, params={"video_id": video_id})
            return {
                "video_id": response.get("id"),
                "title": response.get("title", ""),
                "description": response.get("description", ""),
                "published_at": response.get("published_at"),
                "duration": response.get("duration"),
                "view_count": response.get("view_count", 0),
                "like_count": response.get("like_count", 0),
                "comment_count": response.get("comment_count", 0),
                "channel_id": response.get("channel_id"),
                "channel_title": response.get("channel_title"),
                "tags": response.get("tags", []),
                "category_id": response.get("category_id"),
                "thumbnail_url": response.get("thumbnail_url"),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get YouTube video details for {video_id}: {e}")
            return {}

    def get_youtube_transcript(self, video_id: str) -> Dict[str, Any]:
        """Get video transcript for deep thought analysis"""
        endpoint = "v1/youtube/transcript"
        try:
            response = self._make_request("GET", endpoint, params={"video_id": video_id})
            # Handle both string and structured response
            if isinstance(response, str):
                return {"transcript": response, "language": "", "segments": []}
            return {
                "transcript": response.get("transcript", ""),
                "language": response.get("language", ""),
                "segments": response.get("segments", []),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get YouTube transcript for {video_id}: {e}")
            return {"transcript": "", "language": "", "segments": []}

    def search_youtube(self, query: str, count: int = 20) -> Dict[str, Any]:
        """Search YouTube for videos, channels, and playlists"""
        endpoint = "v1/youtube/search"
        try:
            response = self._make_request("GET", endpoint, params={"query": query, "count": count})
            return {
                "videos": response.get("videos", []),
                "channels": response.get("channels", []),
                "playlists": response.get("playlists", []),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to search YouTube for '{query}': {e}")
            return {"videos": [], "channels": [], "playlists": []}

    def search_youtube_hashtag(self, hashtag: str, count: int = 20) -> List[Dict[str, Any]]:
        """Search YouTube videos by hashtag"""
        endpoint = "v1/youtube/search-hashtag"
        try:
            response = self._make_request("GET", endpoint, params={"hashtag": hashtag, "count": count})
            return response.get("videos", [])
        except Exception as e:
            logger.warning(f"Failed to search YouTube hashtag '{hashtag}': {e}")
            return []

    def get_youtube_comments(self, video_id: str, count: int = 50) -> List[Dict[str, Any]]:
        """Get comments on a YouTube video"""
        endpoint = "v1/youtube/comments"
        try:
            response = self._make_request("GET", endpoint, params={"video_id": video_id, "count": count})
            return response.get("comments", [])
        except Exception as e:
            logger.warning(f"Failed to get YouTube comments for {video_id}: {e}")
            return []

    def get_youtube_trending_shorts(self, count: int = 20) -> List[Dict[str, Any]]:
        """Get trending YouTube Shorts"""
        endpoint = "v1/youtube/trending-shorts"
        try:
            response = self._make_request("GET", endpoint, params={"count": count})
            return response.get("shorts", [])
        except Exception as e:
            logger.warning(f"Failed to get YouTube trending shorts: {e}")
            return []

    def get_youtube_playlist(self, playlist_id: str) -> Dict[str, Any]:
        """Get YouTube playlist details and videos"""
        endpoint = "v1/youtube/playlist"
        try:
            response = self._make_request("GET", endpoint, params={"playlist_id": playlist_id})
            return {
                "playlist_id": response.get("id"),
                "title": response.get("title", ""),
                "description": response.get("description", ""),
                "channel_title": response.get("channel_title"),
                "video_count": response.get("video_count", 0),
                "videos": response.get("videos", []),
                "thumbnail_url": response.get("thumbnail_url"),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get YouTube playlist {playlist_id}: {e}")
            return {}

    def get_youtube_community_post(self, post_id: str) -> Dict[str, Any]:
        """Get YouTube community post details"""
        endpoint = "v1/youtube/community-post"
        try:
            response = self._make_request("GET", endpoint, params={"post_id": post_id})
            return {
                "post_id": response.get("id"),
                "content": response.get("content", ""),
                "like_count": response.get("like_count", 0),
                "comment_count": response.get("comment_count", 0),
                "published_at": response.get("published_at"),
                "author": response.get("author", {}),
                "images": response.get("images", []),
                "poll": response.get("poll"),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get YouTube community post {post_id}: {e}")
            return {}


    # ═══════════════════════════════════════════════════════════════════════════
    # FACEBOOK COMPLETE INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════

    def get_facebook_reels(self, username: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get Facebook reels for a user (real endpoint: /profile/reels, param `url`, paginated)"""
        endpoint = "v1/facebook/profile/reels"
        try:
            reels, cursor = [], None
            for _ in range(7):  # max 7 pages (=count cap) to bound credit use
                params = {"url": self._fb_url(username)}
                if cursor:
                    params["cursor"] = cursor
                response = self._make_request("GET", endpoint, params=params)
                batch = response.get("reels", [])
                if not batch:
                    break
                reels.extend(batch)
                cursor = response.get("cursor") or response.get("next_page_id")
                if not cursor or len(reels) >= count:
                    break
            return reels[:count]
        except Exception as e:
            logger.warning(f"Failed to get Facebook reels for {username}: {e}")
            return reels[:count]  # keep partial results (e.g. credits ran out mid-pagination)

    def get_facebook_posts(self, username: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get Facebook posts for a user (real endpoint: /profile/posts, param `url`, 3/page, paginated)"""
        endpoint = "v1/facebook/profile/posts"
        try:
            posts, cursor = [], None
            for _ in range(11):  # max 11 pages * 3/page = 33 posts, bounds credit use
                params = {"url": self._fb_url(username)}
                if cursor:
                    params["cursor"] = cursor
                response = self._make_request("GET", endpoint, params=params)
                batch = response.get("posts", [])
                if not batch:
                    break
                posts.extend(batch)
                cursor = response.get("cursor")
                if not cursor or len(posts) >= count:
                    break
            return posts[:count]
        except Exception as e:
            logger.warning(f"Failed to get Facebook posts for {username}: {e}")
            return posts[:count]  # keep partial results (e.g. credits ran out mid-pagination)

    def get_facebook_group_posts(self, group_id: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get posts from a Facebook group"""
        endpoint = "v1/facebook/group-posts"
        try:
            response = self._make_request("GET", endpoint, params={"group_id": group_id, "count": count})
            return response.get("posts", [])
        except Exception as e:
            logger.warning(f"Failed to get Facebook group posts for {group_id}: {e}")
            return []

    def get_facebook_post(self, post_id: str) -> Dict[str, Any]:
        """Get detailed information about a Facebook post"""
        endpoint = "v1/facebook/post"
        try:
            response = self._make_request("GET", endpoint, params={"post_id": post_id})
            return {
                "post_id": response.get("id"),
                "content": response.get("content", response.get("message", "")),
                "like_count": response.get("like_count", 0),
                "comment_count": response.get("comment_count", 0),
                "share_count": response.get("share_count", 0),
                "created_at": response.get("created_at"),
                "author": response.get("author", {}),
                "media": response.get("media", []),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get Facebook post {post_id}: {e}")
            return {}

    def get_facebook_transcript(self, video_id: str) -> Dict[str, Any]:
        """Get transcript from a Facebook video"""
        endpoint = "v1/facebook/transcript"
        try:
            response = self._make_request("GET", endpoint, params={"video_id": video_id})
            return {
                "transcript": response.get("transcript", ""),
                "language": response.get("language", ""),
                "segments": response.get("segments", []),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get Facebook transcript for {video_id}: {e}")
            return {"transcript": "", "language": "", "segments": []}

    def get_facebook_comments(self, post_id: str, count: int = 50) -> List[Dict[str, Any]]:
        """Get comments on a Facebook post (real endpoint: /post/comments, param `url`).
        Accepts a post URL or a bare post ID (ID alone 404s — needs URL)."""
        endpoint = "v1/facebook/post/comments"
        url = post_id if str(post_id).startswith(("http://", "https://")) else f"https://www.facebook.com/{post_id}"
        try:
            response = self._make_request("GET", endpoint, params={"url": url})
            return response.get("comments", [])
        except Exception as e:
            logger.warning(f"Failed to get Facebook comments for {post_id}: {e}")
            return []

    # ═══════════════════════════════════════════════════════════════════════════
    # LINKEDIN COMPLETE INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════

    def get_linkedin_company_page(self, company_id: str) -> Dict[str, Any]:
        """Get LinkedIn company page details"""
        endpoint = "v1/linkedin/company"
        try:
            response = self._make_request("GET", endpoint, params={"company_id": company_id})
            return {
                "company_id": response.get("id"),
                "name": response.get("name", ""),
                "description": response.get("description", ""),
                "industry": response.get("industry"),
                "company_size": response.get("company_size"),
                "headquarters": response.get("headquarters"),
                "website": response.get("website"),
                "follower_count": response.get("follower_count", 0),
                "employee_count": response.get("employee_count", 0),
                "logo_url": response.get("logo_url"),
                "banner_url": response.get("banner_url"),
                "specialties": response.get("specialties", []),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get LinkedIn company page for {company_id}: {e}")
            return {}

    def get_linkedin_post(self, post_id: str) -> Dict[str, Any]:
        """Get LinkedIn post details"""
        endpoint = "v1/linkedin/post"
        try:
            response = self._make_request("GET", endpoint, params={"post_id": post_id})
            return {
                "post_id": response.get("id"),
                "content": response.get("content", response.get("commentary", "")),
                "like_count": response.get("like_count", 0),
                "comment_count": response.get("comment_count", 0),
                "share_count": response.get("share_count", 0),
                "created_at": response.get("created_at"),
                "author": response.get("author", {}),
                "media": response.get("media", []),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get LinkedIn post {post_id}: {e}")
            return {}

    # ═══════════════════════════════════════════════════════════════════════════
    # TWITTER COMPLETE INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════

    def get_twitter_tweet_details(self, tweet_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific tweet"""
        endpoint = "v1/twitter/tweet-details"
        try:
            response = self._make_request("GET", endpoint, params={"tweet_id": tweet_id})
            return {
                "tweet_id": response.get("id"),
                "text": response.get("text", response.get("full_text", "")),
                "like_count": response.get("like_count", response.get("favorite_count", 0)),
                "retweet_count": response.get("retweet_count", 0),
                "reply_count": response.get("reply_count", 0),
                "quote_count": response.get("quote_count", 0),
                "view_count": response.get("view_count", 0),
                "created_at": response.get("created_at"),
                "author": response.get("author", {}),
                "media": response.get("media", []),
                "hashtags": response.get("hashtags", []),
                "mentions": response.get("mentions", []),
                "urls": response.get("urls", []),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get Twitter tweet details for {tweet_id}: {e}")
            return {}

    def get_twitter_transcript(self, tweet_id: str) -> Dict[str, Any]:
        """Get transcript from a Twitter video tweet"""
        endpoint = "v1/twitter/transcript"
        try:
            response = self._make_request("GET", endpoint, params={"tweet_id": tweet_id})
            return {
                "transcript": response.get("transcript", ""),
                "language": response.get("language", ""),
                "segments": response.get("segments", []),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get Twitter transcript for {tweet_id}: {e}")
            return {"transcript": "", "language": "", "segments": []}

    def get_twitter_community(self, community_id: str) -> Dict[str, Any]:
        """Get Twitter community details"""
        endpoint = "v1/twitter/community"
        try:
            response = self._make_request("GET", endpoint, params={"community_id": community_id})
            return {
                "community_id": response.get("id"),
                "name": response.get("name", ""),
                "description": response.get("description", ""),
                "member_count": response.get("member_count", 0),
                "created_at": response.get("created_at"),
                "rules": response.get("rules", []),
                "banner_url": response.get("banner_url"),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get Twitter community {community_id}: {e}")
            return {}

    def get_twitter_community_tweets(self, community_id: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get tweets from a Twitter community"""
        endpoint = "v1/twitter/community-tweets"
        try:
            response = self._make_request("GET", endpoint, params={"community_id": community_id, "count": count})
            return response.get("tweets", [])
        except Exception as e:
            logger.warning(f"Failed to get Twitter community tweets for {community_id}: {e}")
            return []

    # ═══════════════════════════════════════════════════════════════════════════
    # REDDIT COMPLETE INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════

    def get_reddit_subreddit_details(self, subreddit: str) -> Dict[str, Any]:
        """Get Reddit subreddit details"""
        endpoint = "v1/reddit/subreddit-details"
        try:
            response = self._make_request("GET", endpoint, params={"subreddit": subreddit})
            return {
                "subreddit": response.get("display_name", subreddit),
                "title": response.get("title", ""),
                "description": response.get("public_description", ""),
                "subscriber_count": response.get("subscribers", 0),
                "active_users": response.get("active_user_count", 0),
                "created_at": response.get("created_utc"),
                "over_18": response.get("over18", False),
                "icon_url": response.get("icon_img"),
                "banner_url": response.get("banner_img"),
                "rules": response.get("rules", []),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get Reddit subreddit details for {subreddit}: {e}")
            return {}

    def get_reddit_subreddit_posts(self, subreddit: str, count: int = 25, sort: str = "hot") -> List[Dict[str, Any]]:
        """Get posts from a Reddit subreddit"""
        endpoint = "v1/reddit/subreddit-posts"
        try:
            response = self._make_request("GET", endpoint, params={"subreddit": subreddit, "count": count, "sort": sort})
            return response.get("posts", [])
        except Exception as e:
            logger.warning(f"Failed to get Reddit subreddit posts for {subreddit}: {e}")
            return []

    def get_reddit_post_comments(self, post_id: str, count: int = 50) -> List[Dict[str, Any]]:
        """Get comments on a Reddit post"""
        endpoint = "v1/reddit/post-comments"
        try:
            response = self._make_request("GET", endpoint, params={"post_id": post_id, "count": count})
            return response.get("comments", [])
        except Exception as e:
            logger.warning(f"Failed to get Reddit comments for {post_id}: {e}")
            return []

    def search_reddit(self, query: str, count: int = 25) -> Dict[str, Any]:
        """Search Reddit for posts and subreddits"""
        endpoint = "v1/reddit/search"
        try:
            response = self._make_request("GET", endpoint, params={"query": query, "count": count})
            return {
                "posts": response.get("posts", []),
                "subreddits": response.get("subreddits", []),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to search Reddit for '{query}': {e}")
            return {"posts": [], "subreddits": []}

    def search_reddit_ads(self, query: str) -> List[Dict[str, Any]]:
        """Search Reddit ads"""
        endpoint = "v1/reddit/search-ads"
        try:
            response = self._make_request("GET", endpoint, params={"query": query})
            return response.get("ads", [])
        except Exception as e:
            logger.warning(f"Failed to search Reddit ads for '{query}': {e}")
            return []

    def get_reddit_ad(self, ad_id: str) -> Dict[str, Any]:
        """Get Reddit ad details"""
        endpoint = "v1/reddit/ad"
        try:
            response = self._make_request("GET", endpoint, params={"ad_id": ad_id})
            return response
        except Exception as e:
            logger.warning(f"Failed to get Reddit ad {ad_id}: {e}")
            return {}

    # ═══════════════════════════════════════════════════════════════════════════
    # THREADS COMPLETE INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════

    def get_threads_posts(self, username: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get Threads posts for a user"""
        endpoint = "v1/threads/posts"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username, "count": count})
            return response.get("posts", [])
        except Exception as e:
            logger.warning(f"Failed to get Threads posts for {username}: {e}")
            return []

    def get_threads_post(self, post_id: str) -> Dict[str, Any]:
        """Get Threads post details"""
        endpoint = "v1/threads/post"
        try:
            response = self._make_request("GET", endpoint, params={"post_id": post_id})
            return {
                "post_id": response.get("id"),
                "content": response.get("content", response.get("text", "")),
                "like_count": response.get("like_count", 0),
                "reply_count": response.get("reply_count", 0),
                "repost_count": response.get("repost_count", 0),
                "created_at": response.get("created_at"),
                "author": response.get("author", {}),
                "media": response.get("media", []),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get Threads post {post_id}: {e}")
            return {}

    def search_threads_users(self, query: str, count: int = 20) -> List[Dict[str, Any]]:
        """Search Threads for users"""
        endpoint = "v1/threads/search-users"
        try:
            response = self._make_request("GET", endpoint, params={"query": query, "count": count})
            return response.get("users", [])
        except Exception as e:
            logger.warning(f"Failed to search Threads users for '{query}': {e}")
            return []

    # ═══════════════════════════════════════════════════════════════════════════
    # BLUESKY COMPLETE INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════

    def get_bluesky_posts(self, username: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get Bluesky posts for a user"""
        endpoint = "v1/bluesky/posts"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username, "count": count})
            return response.get("posts", [])
        except Exception as e:
            logger.warning(f"Failed to get Bluesky posts for {username}: {e}")
            return []

    def get_bluesky_post(self, post_id: str) -> Dict[str, Any]:
        """Get Bluesky post details"""
        endpoint = "v1/bluesky/post"
        try:
            response = self._make_request("GET", endpoint, params={"post_id": post_id})
            return {
                "post_id": response.get("id", response.get("uri")),
                "content": response.get("content", response.get("text", "")),
                "like_count": response.get("like_count", 0),
                "reply_count": response.get("reply_count", 0),
                "repost_count": response.get("repost_count", 0),
                "created_at": response.get("created_at", response.get("indexedAt")),
                "author": response.get("author", {}),
                "embed": response.get("embed"),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get Bluesky post {post_id}: {e}")
            return {}

    # ═══════════════════════════════════════════════════════════════════════════
    # PINTEREST COMPLETE INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════

    def search_pinterest(self, query: str, count: int = 20) -> Dict[str, Any]:
        """Search Pinterest for pins and boards"""
        endpoint = "v1/pinterest/search"
        try:
            response = self._make_request("GET", endpoint, params={"query": query, "count": count})
            return {
                "pins": response.get("pins", []),
                "boards": response.get("boards", []),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to search Pinterest for '{query}': {e}")
            return {"pins": [], "boards": []}

    def get_pinterest_pin(self, pin_id: str) -> Dict[str, Any]:
        """Get Pinterest pin details"""
        endpoint = "v1/pinterest/pin"
        try:
            response = self._make_request("GET", endpoint, params={"pin_id": pin_id})
            return {
                "pin_id": response.get("id"),
                "title": response.get("title", ""),
                "description": response.get("description", ""),
                "link": response.get("link"),
                "save_count": response.get("save_count", 0),
                "comment_count": response.get("comment_count", 0),
                "image_url": response.get("image_url"),
                "author": response.get("pinner", {}),
                "board": response.get("board", {}),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get Pinterest pin {pin_id}: {e}")
            return {}

    def get_pinterest_user_boards(self, username: str) -> List[Dict[str, Any]]:
        """Get Pinterest boards for a user"""
        endpoint = "v1/pinterest/user-boards"
        try:
            response = self._make_request("GET", endpoint, params={"handle": username})
            return response.get("boards", [])
        except Exception as e:
            logger.warning(f"Failed to get Pinterest boards for {username}: {e}")
            return []

    def get_pinterest_board(self, board_id: str) -> Dict[str, Any]:
        """Get Pinterest board details and pins"""
        endpoint = "v1/pinterest/board"
        try:
            response = self._make_request("GET", endpoint, params={"board_id": board_id})
            return {
                "board_id": response.get("id"),
                "name": response.get("name", ""),
                "description": response.get("description", ""),
                "pin_count": response.get("pin_count", 0),
                "follower_count": response.get("follower_count", 0),
                "owner": response.get("owner", {}),
                "pins": response.get("pins", []),
                "image_url": response.get("image_cover_url"),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get Pinterest board {board_id}: {e}")
            return {}

    # ═══════════════════════════════════════════════════════════════════════════
    # TWITCH COMPLETE INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════

    def get_twitch_clip(self, clip_id: str) -> Dict[str, Any]:
        """Get Twitch clip details"""
        endpoint = "v1/twitch/clip"
        try:
            response = self._make_request("GET", endpoint, params={"clip_id": clip_id})
            return {
                "clip_id": response.get("id"),
                "title": response.get("title", ""),
                "broadcaster": response.get("broadcaster", {}),
                "creator": response.get("creator", {}),
                "view_count": response.get("view_count", 0),
                "duration": response.get("duration"),
                "created_at": response.get("created_at"),
                "thumbnail_url": response.get("thumbnail_url"),
                "clip_url": response.get("url"),
                "game": response.get("game", {}),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get Twitch clip {clip_id}: {e}")
            return {}

    # ═══════════════════════════════════════════════════════════════════════════
    # KICK COMPLETE INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════

    def get_kick_clip(self, clip_id: str) -> Dict[str, Any]:
        """Get Kick clip details"""
        endpoint = "v1/kick/clip"
        try:
            response = self._make_request("GET", endpoint, params={"clip_id": clip_id})
            return {
                "clip_id": response.get("id"),
                "title": response.get("title", ""),
                "channel": response.get("channel", {}),
                "creator": response.get("creator", {}),
                "view_count": response.get("view_count", 0),
                "duration": response.get("duration"),
                "created_at": response.get("created_at"),
                "thumbnail_url": response.get("thumbnail_url"),
                "clip_url": response.get("clip_url"),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get Kick clip {clip_id}: {e}")
            return {}

    # ═══════════════════════════════════════════════════════════════════════════
    # TIKTOK SHOP COMPLETE INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════

    def search_tiktok_shop(self, query: str, count: int = 20) -> List[Dict[str, Any]]:
        """Search TikTok Shop for products"""
        endpoint = "v1/tiktok-shop/search"
        try:
            response = self._make_request("GET", endpoint, params={"query": query, "count": count})
            return response.get("products", [])
        except Exception as e:
            logger.warning(f"Failed to search TikTok Shop for '{query}': {e}")
            return []

    def get_tiktok_shop_products(self, shop_id: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get products from a TikTok Shop"""
        endpoint = "v1/tiktok-shop/products"
        try:
            response = self._make_request("GET", endpoint, params={"shop_id": shop_id, "count": count})
            return response.get("products", [])
        except Exception as e:
            logger.warning(f"Failed to get TikTok Shop products for {shop_id}: {e}")
            return []

    def get_tiktok_shop_product_details(self, product_id: str) -> Dict[str, Any]:
        """Get detailed information about a TikTok Shop product"""
        endpoint = "v1/tiktok-shop/product-details"
        try:
            response = self._make_request("GET", endpoint, params={"product_id": product_id})
            return {
                "product_id": response.get("id"),
                "title": response.get("title", ""),
                "description": response.get("description", ""),
                "price": response.get("price"),
                "original_price": response.get("original_price"),
                "currency": response.get("currency", "USD"),
                "rating": response.get("rating"),
                "review_count": response.get("review_count", 0),
                "sold_count": response.get("sold_count", 0),
                "images": response.get("images", []),
                "shop": response.get("shop", {}),
                "category": response.get("category"),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to get TikTok Shop product details for {product_id}: {e}")
            return {}

    # ═══════════════════════════════════════════════════════════════════════════
    # AMAZON SHOP COMPLETE INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════

    def get_amazon_shop_products(self, storefront_id: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get products from an Amazon influencer storefront"""
        endpoint = "v1/amazon-shop/products"
        try:
            response = self._make_request("GET", endpoint, params={"storefront_id": storefront_id, "count": count})
            return response.get("products", [])
        except Exception as e:
            logger.warning(f"Failed to get Amazon Shop products for {storefront_id}: {e}")
            return []

    # ═══════════════════════════════════════════════════════════════════════════
    # GOOGLE SEARCH INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════

    def search_google(self, query: str, count: int = 10) -> Dict[str, Any]:
        """Search Google for web results"""
        endpoint = "v1/google/search"
        try:
            response = self._make_request("GET", endpoint, params={"query": query, "count": count})
            return {
                "results": response.get("results", []),
                "total_results": response.get("total_results", 0),
                "raw": response
            }
        except Exception as e:
            logger.warning(f"Failed to search Google for '{query}': {e}")
            return {"results": [], "total_results": 0}

    # --- Utility Endpoints ---
    def get_age_and_gender(self, image_url: str) -> Dict[str, Any]:
        """Predict age and gender from an image URL"""
        endpoint = "v1/age-and-gender/predict"
        try:
            response = self._make_request("GET", endpoint, params={"image_url": image_url})
            return response
        except Exception as e:
            logger.error(f"Failed to predict age/gender: {e}")
            raise

    def _normalize_generic_data(self, data: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """Generic normalizer for platforms without custom normalization.
        Facebook raw fields (verified live): followerCount/likeCount/
        talkingAboutCount (camelCase), pageIntro (bio), category,
        profilePicLarge/Medium (URL strings), id (numeric FB id)."""
        return {
            "user_id": data.get("id") or data.get("user_id") or data.get("handle"),
            "username": data.get("username") or data.get("handle") or data.get("id"),
            "display_name": data.get("name") or data.get("display_name") or data.get("full_name"),
            "bio": data.get("bio") or data.get("pageIntro") or data.get("description") or data.get("about"),
            "follower_count": data.get("followerCount") or data.get("followers") or data.get("follower_count") or data.get("followers_count") or 0,
            "following_count": data.get("following") or data.get("following_count") or 0,
            "posts_count": data.get("posts_count") or data.get("media_count") or data.get("videos_count") or 0,
            "verified": data.get("verified") or data.get("is_verified") or False,
            "profile_image_url": data.get("profilePicLarge") or data.get("profilePicMedium") or data.get("avatar") or data.get("profile_image_url") or data.get("avatar_url"),
            # Facebook-specific (real, from API — no fabrication):
            "like_count": data.get("likeCount"),
            "talking_about_count": data.get("talkingAboutCount"),
            "category": data.get("category"),
            "gender": data.get("gender"),
            "profile_url": data.get("url"),
            "metadata": {
                "platform": platform,
                "is_real_data": True
            },
            "raw": data
        }

    def collect_facebook_deep(self, username: str, max_post_pages: int = 11, max_comment_posts: int = 2) -> Dict[str, Any]:
        """Deep Facebook collection: profile + paginated posts + reels + photos
        + events + comments on top posts. Credit-aware: ~4 + pages + comments
        credits. Every sub-call degrades gracefully (empty list, not crash),
        so one failing endpoint never kills the whole profile."""
        fb_url = self._fb_url(username)
        deep: Dict[str, Any] = {"profile": None, "posts": [], "reels": [], "photos": [], "events": [], "comments": [], "errors": []}
        try:
            deep["profile"] = self.get_facebook_profile(username)
        except Exception as e:
            deep["errors"].append(f"profile: {str(e)[:200]}")
        # Posts with cursor pagination (3/page per API)
        cursor = None
        for _ in range(max_post_pages):
            try:
                params = {"url": fb_url}
                if cursor:
                    params["cursor"] = cursor
                resp = self._make_request("GET", "v1/facebook/profile/posts", params=params)
                batch = resp.get("posts", [])
                if not batch:
                    break
                deep["posts"].extend(batch)
                cursor = resp.get("cursor")
                if not cursor:
                    break
            except Exception as e:
                deep["errors"].append(f"posts: {str(e)[:200]}")
                break
        # Reels / photos / events (1 page each)
        for key, endpoint in [("reels", "v1/facebook/profile/reels"), ("photos", "v1/facebook/profile/photos"), ("events", "v1/facebook/profile/events")]:
            try:
                resp = self._make_request("GET", endpoint, params={"url": fb_url})
                deep[key] = resp.get(key, [])
            except Exception as e:
                deep["errors"].append(f"{key}: {str(e)[:200]}")
        # Comments on the most recent posts that have comments
        for post in deep["posts"][:max_comment_posts]:
            post_url = post.get("url") or post.get("permalink")
            if not post_url or str(post.get("commentCount", "0")) == "0":
                continue
            try:
                resp = self._make_request("GET", "v1/facebook/post/comments", params={"url": post_url})
                deep["comments"].extend(resp.get("comments", []))
            except Exception as e:
                deep["errors"].append(f"comments: {str(e)[:200]}")
        return deep


    
    def get_twitter_posts(self, username: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get Twitter posts"""
        endpoint = "v1/twitter/user-tweets"
        
        try:
            response = self._make_request("GET", endpoint, params={"handle": username, "count": count})
            return [self._normalize_twitter_post(post) for post in response.get("posts", response.get("tweets", []))]
        except Exception as e:
            logger.error(f"Failed to get Twitter posts for {username}: {e}")
            raise

    
    def _normalize_twitter_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Twitter profile data to standard format"""
        return {
            "platform": "twitter",
            "id": data.get("id"),
            "username": data.get("username"),
            "display_name": data.get("name", data.get("display_name")),
            "bio": data.get("description", data.get("bio", "")),
            "location": data.get("location", ""),
            "followers_count": data.get("followers_count", 0),
            "following_count": data.get("following_count", 0),
            "posts_count": data.get("tweet_count", data.get("posts_count", 0)),
            "verified": data.get("verified", False),
            "created_at": data.get("created_at"),
            "profile_image_url": data.get("profile_image_url"),
            "banner_url": data.get("banner_url"),
            "website_url": data.get("url"),
            "raw_data": data  # Keep original data for reference
        }
    
    def _normalize_instagram_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Instagram profile data to standard format"""
        return {
            "platform": "instagram",
            "id": data.get("id"),
            "username": data.get("username"),
            "display_name": data.get("full_name", data.get("name")),
            "bio": data.get("biography", ""),
            "location": "",  # Instagram doesn't provide location in profile
            "followers_count": data.get("followers_count", 0),
            "following_count": data.get("following_count", 0),
            "posts_count": data.get("media_count", 0),
            "verified": data.get("is_verified", False),
            "created_at": None,  # Instagram doesn't provide creation date
            "profile_image_url": data.get("profile_pic_url"),
            "website_url": data.get("external_url"),
            "is_private": data.get("is_private", False),
            "is_business": data.get("is_business_account", False),
            "raw_data": data
        }
    
    def _normalize_linkedin_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize LinkedIn profile data to standard format"""
        return {
            "platform": "linkedin",
            "id": data.get("id"),
            "username": data.get("username", data.get("public_identifier")),
            "display_name": f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
            "bio": data.get("summary", data.get("headline", "")),
            "location": data.get("location", ""),
            "followers_count": data.get("followers_count", 0),
            "connections_count": data.get("connections_count", 0),
            "posts_count": 0,  # LinkedIn doesn't provide post count in profile
            "verified": False,  # LinkedIn doesn't have verification badges
            "profile_image_url": data.get("profile_image_url"),
            "industry": data.get("industry"),
            "current_position": data.get("current_position"),
            "company": data.get("company"),
            "raw_data": data
        }
    
    def _normalize_tiktok_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize TikTok profile data to standard format"""
        return {
            "platform": "tiktok",
            "id": data.get("id"),
            "username": data.get("unique_id", data.get("username")),
            "display_name": data.get("nickname", data.get("display_name")),
            "bio": data.get("signature", ""),
            "followers_count": data.get("follower_count", 0),
            "following_count": data.get("following_count", 0),
            "posts_count": data.get("video_count", 0),
            "likes_count": data.get("heart_count", 0),
            "verified": data.get("verified", False),
            "profile_image_url": data.get("avatar_larger"),
            "is_private": data.get("secret", False),
            "raw_data": data
        }
    
    def _normalize_youtube_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize YouTube profile data to standard format"""
        return {
            "platform": "youtube",
            "id": data.get("id"),
            "username": data.get("custom_url", data.get("username")),
            "display_name": data.get("title", data.get("name")),
            "bio": data.get("description", ""),
            "subscribers_count": data.get("subscriber_count", 0),
            "video_count": data.get("video_count", 0),
            "view_count": data.get("view_count", 0),
            "verified": data.get("verified", False),
            "profile_image_url": data.get("thumbnail_url"),
            "banner_url": data.get("banner_url"),
            "country": data.get("country"),
            "created_at": data.get("published_at"),
            "raw_data": data
        }
    
    def _normalize_snapchat_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Snapchat profile data to standard format"""
        return {
            "platform": "snapchat",
            "id": data.get("id"),
            "username": data.get("username"),
            "display_name": data.get("display_name"),
            "bio": data.get("bio", ""),
            "snapcode_url": data.get("snapcode_url"),
            "profile_image_url": data.get("profile_image_url"),
            "verified": data.get("verified", False),
            "raw_data": data
        }
    
    def _normalize_pinterest_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Pinterest profile data to standard format"""
        return {
            "platform": "pinterest",
            "id": data.get("id"),
            "username": data.get("username"),
            "display_name": data.get("full_name", data.get("name")),
            "bio": data.get("about", ""),
            "followers_count": data.get("follower_count", 0),
            "following_count": data.get("following_count", 0),
            "board_count": data.get("board_count", 0),
            "pin_count": data.get("pin_count", 0),
            "verified": data.get("verified", False),
            "profile_image_url": data.get("image_medium_url"),
            "website_url": data.get("website_url"),
            "location": data.get("location"),
            "raw_data": data
        }
    
    def _normalize_reddit_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Reddit profile data to standard format"""
        return {
            "platform": "reddit",
            "id": data.get("id"),
            "username": data.get("name"),
            "display_name": data.get("subreddit", {}).get("display_name"),
            "bio": data.get("subreddit", {}).get("public_description", ""),
            "comment_karma": data.get("comment_karma", 0),
            "link_karma": data.get("link_karma", 0),
            "total_karma": data.get("total_karma", 0),
            "created_at": data.get("created_utc"),
            "verified": data.get("verified", False),
            "profile_image_url": data.get("icon_img"),
            "is_gold": data.get("is_gold", False),
            "is_mod": data.get("is_mod", False),
            "raw_data": data
        }
    
    def _normalize_github_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize GitHub profile data to standard format"""
        return {
            "platform": "github",
            "id": data.get("id"),
            "username": data.get("login"),
            "display_name": data.get("name"),
            "bio": data.get("bio", ""),
            "location": data.get("location"),
            "followers_count": data.get("followers", 0),
            "following_count": data.get("following", 0),
            "public_repos": data.get("public_repos", 0),
            "public_gists": data.get("public_gists", 0),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "profile_image_url": data.get("avatar_url"),
            "website_url": data.get("blog"),
            "company": data.get("company"),
            "hireable": data.get("hireable", False),
            "raw_data": data
        }
    
    def _normalize_twitter_post(self, post: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Twitter post data"""
        return {
            "id": post.get("id"),
            "text": post.get("text", post.get("full_text", "")),
            "created_at": post.get("created_at"),
            "likes_count": post.get("favorite_count", post.get("likes", 0)),
            "retweets_count": post.get("retweet_count", post.get("retweets", 0)),
            "replies_count": post.get("reply_count", post.get("replies", 0)),
            "is_retweet": post.get("is_retweet", False),
            "media": post.get("media", []),
            "hashtags": post.get("hashtags", []),
            "mentions": post.get("mentions", []),
            "raw_data": post
        }

# =============================================================================
# Apify Actor client (real integration)
# =============================================================================
# Apify = DATA COLLECTION (scraping). OpenRouter = LLM ANALYSIS. They are
# orthogonal: Apify cannot do psychological/sentiment analysis, OpenRouter
# cannot scrape profiles. Vanta uses both: Apify/ScrapeCreators fetch data,
# OpenRouter analyses it.
# Auth: Authorization: Bearer $APIFY_API_TOKEN (Console > Settings > Integrations)
# Run: POST https://api.apify.com/v2/acts/{actorId}/run-sync-get-dataset-items
class ApifyError(Exception):
    pass


# Verified public actors (Apify Store). Override any via APIFY_ACTOR_<PLATFORM>,
# e.g. APIFY_ACTOR_TWITTER=someuser/twitter-scraper
APIFY_ACTORS = {
    "tiktok": "clockworks/tiktok-scraper",
    "instagram": "apify/instagram-scraper",
    "facebook": "apify/facebook-posts-scraper",  # verified live 200 via Apify API; old apify/facebook-scraper 404s
    "youtube": "streamers/youtube-scraper",
    "twitter": "quikr/twitter-scraper",
}


class ApifyClient:
    def __init__(self, token=None):
        self.api_token = token or os.getenv("APIFY_API_TOKEN") or os.getenv("APIFY_TOKEN")
        if self.api_token and self.api_token.startswith("your_"):
            self.api_token = None
        self.base_url = os.getenv("APIFY_BASE_URL", "https://api.apify.com/v2")
        self.session = requests.Session()
        if self.api_token:
            self.session.headers.update({"Authorization": f"Bearer {self.api_token}"})

    @property
    def is_configured(self):
        return bool(self.api_token)

    def check_token(self):
        """GET /users/me — cheap auth check, no Actor run / no cost."""
        if not self.is_configured:
            return {"configured": False, "valid": False}
        r = self.session.get(f"{self.base_url}/users/me", timeout=15)
        return {"configured": True, "valid": r.status_code == 200, "status": r.status_code,
                "user": r.json().get("data", {}).get("username") if r.ok else None}

    def run_actor(self, actor_id, actor_input, timeout=120):
        """Synchronously run an Actor and return dataset items (list)."""
        if not self.is_configured:
            raise ApifyError("APIFY_API_TOKEN not configured")
        actor = actor_id.replace("/", "~")  # API accepts user~name in path
        url = f"{self.base_url}/acts/{actor}/run-sync-get-dataset-items"
        r = self.session.post(url, json=actor_input, timeout=timeout)
        if r.status_code == 401:
            raise ApifyError("Invalid Apify token (401)")
        if r.status_code == 403:
            raise ApifyError(f"Actor not approved / forbidden (403): {r.text[:200]}")
        if r.status_code not in (200, 201):  # 201 = run accepted, items in body (facebook-posts-scraper)
            raise ApifyError(f"Apify {r.status_code}: {r.text[:300]}")
        data = r.json()
        return data if isinstance(data, list) else data.get("data", {}).get("items", data)

    def scrape_profile(self, platform, username, max_results=20):
        platform = platform.lower()
        actor_id = os.getenv(f"APIFY_ACTOR_{platform.upper()}", APIFY_ACTORS.get(platform))
        if not actor_id:
            raise ApifyError(f"No Apify actor configured for '{platform}' (set APIFY_ACTOR_{platform.upper()})")
        # Generic, actor-agnostic input: most scrapers accept startUrls/profile URLs.
        # Actors needing a different schema can be swapped via env actor id and
        # the caller can use run_actor() directly with the exact schema.
        profile_url = f"https://{platform}.com/{username}"
        actor_input = {"startUrls": [{"url": profile_url}], "maxResults": max_results, "profiles": [username]}
        items = self.run_actor(actor_id, actor_input)
        return {"platform": platform, "username": username, "actor": actor_id, "items": items, "count": len(items) if isinstance(items, list) else 0}

    def scrape_facebook(self, username: str, max_results: int = 30) -> Dict[str, Any]:
        """Fallback Facebook collection via apify/facebook-posts-scraper (verified live).
        Returns {'profile': {...}, 'posts': [...]} normalized to the dossier shape.
        Counts are only set when the actor actually returns them — never invented."""
        actor_id = os.getenv("APIFY_ACTOR_FACEBOOK", APIFY_ACTORS.get("facebook"))
        if not actor_id:
            raise ApifyError("No Apify actor configured for 'facebook' (set APIFY_ACTOR_FACEBOOK)")
        profile_url = f"https://www.facebook.com/{username.lstrip('@')}"
        items = self.run_actor(actor_id, {"startUrls": [{"url": profile_url}], "maxResults": max_results})
        if not isinstance(items, list):
            items = []
        posts = []
        profile = {"username": username, "profile_url": profile_url, "metadata": {"platform": "facebook", "is_real_data": True, "provider": "apify", "actor": actor_id}}
        for it in items:
            if not isinstance(it, dict):
                continue
            author = it.get("author") or it.get("user") or {}
            if isinstance(author, dict):
                profile.setdefault("display_name", author.get("name") or author.get("fullName"))
                profile.setdefault("profile_image_url", author.get("profilePicture") or author.get("profilePic"))
            text = it.get("text") or it.get("caption") or it.get("content") or ""
            posts.append({
                "id": it.get("id") or it.get("postId") or it.get("url"),
                "text": text, "content": text,
                "url": it.get("url") or it.get("postUrl"),
                "created_at": it.get("time") or it.get("timestamp") or it.get("date"),
                "likes_count": it.get("likes") or it.get("likesCount"),
                "comments_count": it.get("commentsCount") or it.get("comments"),
                "shares_count": it.get("shares") or it.get("sharesCount"),
            })
        # Only surface counts the actor returned
        first = items[0] if items and isinstance(items[0], dict) else {}
        for src, dst in [("followerCount", "follower_count"), ("followers", "follower_count"), ("likeCount", "like_count")]:
            if first.get(src) is not None:
                profile[dst] = first[src]
        return {"profile": profile, "posts": posts, "actor": actor_id, "count": len(posts)}


def get_apify_client():
    return ApifyClient()


# Fallback mock client for testing when API key is not available
class MockScrapeCreatorsClient:
    """Mock client for testing without API key"""
    
    def get_twitter_profile(self, username: str) -> Dict[str, Any]:
        return {
            "platform": "twitter",
            "username": username,
            "display_name": f"Mock {username.title()}",
            "bio": f"This is a mock profile for {username}",
            "followers_count": 10000,
            "following_count": 500,
            "posts_count": 1000,
            "verified": False,
            "created_at": "2020-01-01T00:00:00Z"
        }
    
    def get_twitter_posts(self, username: str, count: int = 20) -> List[Dict[str, Any]]:
        return [
            {
                "id": f"mock_{i}",
                "text": f"Mock tweet {i} from {username}",
                "likes_count": 10 * i,
                "retweets_count": 5 * i,
                "replies_count": 2 * i
            }
            for i in range(1, count + 1)
        ]

    def __getattr__(self, name):
        """Dynamic mock data generator for other platforms"""
        if name.startswith("get_") and name.endswith("_profile"):
            platform = name[4:-8]
            
            def mock_profile_fetcher(username: str) -> Dict[str, Any]:
                return {
                    "platform": platform,
                    "username": username,
                    "display_name": f"Mock {platform.title()} User",
                    "bio": f"Mock bio for {username} on {platform}",
                    "followers_count": 5000,
                    "following_count": 100,
                    "posts_count": 50,
                    "verified": False,
                    "raw_data": {"mock": True}
                }
            return mock_profile_fetcher
        
        # Default behavior for other attributes
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

def get_scrape_client() -> ScrapeCreatorsClient:
    """Get ScrapeCreators client instance"""
    client = ScrapeCreatorsClient()
    
    # Return mock client if API key not configured
    if not client.api_key:
        logger.warning("Using mock ScrapeCreators client - add real API key for production")
        return MockScrapeCreatorsClient()
    
    return client