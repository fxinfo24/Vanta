"""
Vanta Deep Dossier Collector
Orchestrates comprehensive data collection across all platforms.
Supports Quick Scan (10s) and Deep Dossier (2-5 min) analysis modes.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from .scrape_client import ScrapeCreatorsClient, get_scrape_client, ScrapeCreatorsError

logger = logging.getLogger(__name__)


def content_key(item: Dict[str, Any]) -> str:
    """One stable identity per content item across feed endpoints.

    The same reel is served by the posts feed as a post id and by the reels
    feed as an opaque encoded id, so ids cannot be compared directly: the
    canonical URL can. Doubled items inflate `posts_measured`, which is the
    denominator of the engagement rate, and make the comments step pay twice
    for the same post.
    """
    if not isinstance(item, dict):
        return ""
    url = str(item.get("url") or item.get("permalink") or item.get("post_url") or "").strip()
    if url:
        no_query = url.split("?", 1)[0].rstrip("/")
        if no_query:
            return no_query.lower()
    for field in ("id", "post_id", "video_id", "shortcode"):
        value = item.get(field)
        if value:
            return f"id:{value}"
    return ""


def _richness(item: Dict[str, Any]) -> int:
    """How much usable data an item carries; richer duplicates are kept."""
    if not isinstance(item, dict):
        return 0
    score = 0
    for field in ("reactionCount", "reaction_count", "commentCount", "comment_count",
                  "share_count", "shares", "view_count", "videoDetails", "image"):
        if item.get(field) not in (None, "", [], {}):
            score += 1
    text = item.get("text") or item.get("message") or item.get("caption") or ""
    if isinstance(text, str) and text.strip():
        score += 1
    return score


def dedupe_content(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Drop repeated items, keeping the richest copy. Returns (items, removed)."""
    kept, index, removed = [], {}, 0
    for item in items or []:
        key = content_key(item)
        if not key:
            kept.append(item)
            continue
        if key not in index:
            index[key] = len(kept)
            kept.append(item)
            continue
        removed += 1
        position = index[key]
        if _richness(item) > _richness(kept[position]):
            kept[position] = item
    return kept, removed


class DeepDossierCollector:
    """
    Master orchestrator for comprehensive digital intelligence collection.
    
    Modes:
    - Quick Scan: Profile + Recent 10 posts (10 seconds)
    - Deep Dossier: Everything available (2-5 minutes)
    """
    
    # Platform configurations
    SUPPORTED_PLATFORMS = {
        'tiktok': {
            'name': 'TikTok',
            'profile_method': 'get_tiktok_profile',
            'deep_methods': [
                ('videos', 'get_tiktok_videos', {'count': 30}),
                ('demographics', 'get_tiktok_audience_demographics', {}),
                ('followers_sample', 'get_tiktok_followers', {'count': 100}),
                ('following_sample', 'get_tiktok_following', {'count': 100}),
                ('live_status', 'get_tiktok_live', {}),
            ],
            'content_method': 'get_tiktok_videos',
            'comments_method': 'get_tiktok_comments',
            'transcript_method': 'get_tiktok_transcript',
        },
        'instagram': {
            'name': 'Instagram',
            'profile_method': 'get_instagram_profile',
            'deep_methods': [
                ('posts', 'get_instagram_posts_deep', {'count': 20}),
                ('reels', 'get_instagram_reels', {'count': 20}),
                ('highlights', 'get_instagram_story_highlights', {}),
            ],
            'content_method': 'get_instagram_posts_deep',
            'comments_method': 'get_instagram_comments',
            'transcript_method': 'get_instagram_transcript',
        },
        'youtube': {
            'name': 'YouTube',
            'profile_method': 'get_youtube_profile',
            'deep_methods': [
                ('videos', 'get_youtube_videos_deep', {'count': 30}),
                ('shorts', 'get_youtube_channel_shorts', {'count': 20}),
                ('channel_details', 'get_youtube_channel_details', {}),
            ],
            'content_method': 'get_youtube_videos_deep',
            'comments_method': 'get_youtube_comments',
            'transcript_method': 'get_youtube_transcript',
        },
        'twitter': {
            'name': 'Twitter/X',
            'profile_method': 'get_twitter_profile',
            'deep_methods': [
                ('tweets', 'get_twitter_posts', {'count': 50}),
            ],
            'content_method': 'get_twitter_posts',
            'comments_method': None,
            'transcript_method': 'get_twitter_transcript',
        },
        'facebook': {
            'name': 'Facebook',
            'profile_method': 'get_facebook_profile',
            'deep_methods': [
                ('posts', 'get_facebook_posts', {'count': 30}),
                ('reels', 'get_facebook_reels', {'count': 20}),
            ],
            'content_method': 'get_facebook_posts',
            'comments_method': 'get_facebook_comments',
            'transcript_method': 'get_facebook_transcript',
        },
        'linkedin': {
            'name': 'LinkedIn',
            'profile_method': 'get_linkedin_profile',
            'deep_methods': [],
            'content_method': None,
            'comments_method': None,
            'transcript_method': None,
        },
        'reddit': {
            'name': 'Reddit',
            'profile_method': 'get_reddit_profile',
            'deep_methods': [],
            'content_method': None,
            'comments_method': 'get_reddit_post_comments',
            'transcript_method': None,
        },
        'threads': {
            'name': 'Threads',
            'profile_method': 'get_threads_profile',
            'deep_methods': [
                ('posts', 'get_threads_posts', {'count': 30}),
            ],
            'content_method': 'get_threads_posts',
            'comments_method': None,
            'transcript_method': None,
        },
        'bluesky': {
            'name': 'Bluesky',
            'profile_method': 'get_bluesky_profile',
            'deep_methods': [
                ('posts', 'get_bluesky_posts', {'count': 30}),
            ],
            'content_method': 'get_bluesky_posts',
            'comments_method': None,
            'transcript_method': None,
        },
        'pinterest': {
            'name': 'Pinterest',
            'profile_method': 'get_pinterest_profile',
            'deep_methods': [
                ('boards', 'get_pinterest_user_boards', {}),
            ],
            'content_method': None,
            'comments_method': None,
            'transcript_method': None,
        },
        'twitch': {
            'name': 'Twitch',
            'profile_method': 'get_twitch_profile',
            'deep_methods': [],
            'content_method': None,
            'comments_method': None,
            'transcript_method': None,
        },
        'kick': {
            'name': 'Kick',
            'profile_method': 'get_kick_profile',
            'deep_methods': [],
            'content_method': None,
            'comments_method': None,
            'transcript_method': None,
        },
        'snapchat': {
            'name': 'Snapchat',
            'profile_method': 'get_snapchat_profile',
            'deep_methods': [],
            'content_method': None,
            'comments_method': None,
            'transcript_method': None,
        },
        'github': {
            'name': 'GitHub',
            'profile_method': 'get_github_profile',
            'deep_methods': [],
            'content_method': None,
            'comments_method': None,
            'transcript_method': None,
        },
        'linktree': {
            'name': 'Linktree',
            'profile_method': 'get_linktree_profile',
            'deep_methods': [],
            'content_method': None,
            'comments_method': None,
            'transcript_method': None,
        },
        'tiktok_shop': {
            'name': 'TikTok Shop',
            'profile_method': 'get_tiktok_shop_profile',
            'deep_methods': [
                ('products', 'get_tiktok_shop_products', {'count': 50}),
            ],
            'content_method': None,
            'comments_method': None,
            'transcript_method': None,
        },
        'amazon_shop': {
            'name': 'Amazon Shop',
            'profile_method': 'get_amazon_shop_profile',
            'deep_methods': [
                ('products', 'get_amazon_shop_products', {'count': 50}),
            ],
            'content_method': None,
            'comments_method': None,
            'transcript_method': None,
        },
        'google': {
            'name': 'Google',
            'profile_method': 'get_google_profile',
            'deep_methods': [
                ('search_results', 'search_google', {'count': 20}),
            ],
            'content_method': None,
            'comments_method': None,
            'transcript_method': None,
        },
        'komi': {
            'name': 'Komi',
            'profile_method': 'get_komi_profile',
            'deep_methods': [],
            'content_method': None,
            'comments_method': None,
            'transcript_method': None,
        },
        'pillar': {
            'name': 'Pillar',
            'profile_method': 'get_pillar_profile',
            'deep_methods': [],
            'content_method': None,
            'comments_method': None,
            'transcript_method': None,
        },
        'linkbio': {
            'name': 'Linkbio',
            'profile_method': 'get_linkbio_profile',
            'deep_methods': [],
            'content_method': None,
            'comments_method': None,
            'transcript_method': None,
        },
    }

    def __init__(self, client: ScrapeCreatorsClient = None):
        """Initialize with ScrapeCreators client"""
        self.client = client or get_scrape_client()
        self.collection_start_time = None

    def _apify_facebook_fallback(self, username: str, result: Dict[str, Any]) -> bool:
        """Collect Facebook profile+posts via Apify when ScrapeCreators credits are out.
        Returns True on success (result['profile']/['content'] populated)."""
        try:
            from .scrape_client import get_apify_client
            apify = get_apify_client()
            if not apify.is_configured:
                logger.warning("Apify fallback unavailable: APIFY_API_TOKEN not configured")
                return False
            data = apify.scrape_facebook(username, max_results=30)
            if not data.get("posts") and not data.get("profile"):
                return False
            result['profile'] = data.get('profile')
            result['content'] = data.get('posts') or []
            result['additional_data']['provider'] = 'apify'
            result['additional_data']['apify_actor'] = data.get('actor')
            result['additional_data']['apify_fallback'] = True
            logger.info(f"Apify Facebook fallback collected {len(result['content'])} posts for {username}")
            return True
        except Exception as e:
            logger.warning(f"Apify Facebook fallback failed for {username}: {e}")
            return False

    def _finalize_dossier(self, result: Dict[str, Any], api_calls: int) -> Dict[str, Any]:
        """Fill statistics on a dossier and return it (used by the Apify fallback path)."""
        result['statistics']['api_calls_made'] = api_calls
        result['statistics']['content_items_collected'] = len(result.get('content') or [])
        result['statistics']['comments_collected'] = result.get('comments_analysis', {}).get('total_comments_collected', 0)
        result['statistics']['transcripts_collected'] = len(result.get('transcripts') or [])
        if self.collection_start_time:
            result['collection_time_seconds'] = round(time.time() - self.collection_start_time, 2)
        logger.info(f"Deep dossier completed (fallback path) in {result['collection_time_seconds']}s with {api_calls} API calls")
        return result
        
    def quick_scan(self, platform: str, username: str) -> Dict[str, Any]:
        """
        Perform a quick 10-second scan.
        Collects: Profile + Recent 10 posts
        
        Args:
            platform: Platform identifier (e.g., 'tiktok', 'instagram')
            username: Username/handle on the platform
            
        Returns:
            Dict with profile and recent content
        """
        self.collection_start_time = time.time()
        logger.info(f"Starting QUICK SCAN for {username} on {platform}")
        
        result = {
            'collection_mode': 'quick_scan',
            'platform': platform,
            'username': username,
            'collected_at': datetime.utcnow().isoformat(),
            'profile': None,
            # Canonical key: every downstream analyzer and the coverage report
            # read `content`. A quick scan used to write `recent_content`, so
            # collected posts were silently analysed as zero posts.
            'content': [],
            'errors': [],
            'collection_time_seconds': 0,
        }
        
        if platform not in self.SUPPORTED_PLATFORMS:
            result['errors'].append(f"Unsupported platform: {platform}")
            return result
            
        config = self.SUPPORTED_PLATFORMS[platform]
        
        # 1. Get profile
        try:
            profile_method = getattr(self.client, config['profile_method'], None)
            if profile_method:
                result['profile'] = profile_method(username)
                logger.info(f"Profile collected for {username}")
        except Exception as e:
            # Same credits-exhausted fallback the deep path uses, so a quick run
            # does not come back empty while a working provider is configured.
            if platform == 'facebook' and 'CREDITS_EXHAUSTED' in str(e):
                logger.warning(f"ScrapeCreators credits exhausted for {username}; trying Apify Facebook fallback...")
                if self._apify_facebook_fallback(username, result):
                    result['errors'].append('ScrapeCreators credits exhausted; served via Apify fallback')
                    result['collection_time_seconds'] = round(time.time() - self.collection_start_time, 2)
                    logger.info(f"Quick scan completed via Apify fallback with {len(result['content'])} items")
                    return result
                result['errors'].append(f"Profile error (credits exhausted, Apify fallback failed): {str(e)}")
                result['collection_time_seconds'] = round(time.time() - self.collection_start_time, 2)
                return result
            result['errors'].append(f"Profile error: {str(e)}")
            logger.warning(f"Failed to get profile for {username}: {e}")
        
        # 2. Get recent content (10 items)
        try:
            if config.get('content_method'):
                content_method = getattr(self.client, config['content_method'], None)
                if content_method:
                    result['content'] = content_method(username, count=10)
                    logger.info(f"Collected {len(result['content'])} recent items")
        except Exception as e:
            result['errors'].append(f"Content error: {str(e)}")
            logger.warning(f"Failed to get content for {username}: {e}")
        
        result['collection_time_seconds'] = round(time.time() - self.collection_start_time, 2)
        logger.info(f"Quick scan completed in {result['collection_time_seconds']}s")
        
        return result
    
    @staticmethod
    def _stage(on_stage, name: str, note: str, done: int = None, total: int = None) -> None:
        """Tell a caller what just happened, never how long anything should take.

        Progress here is counted work (feeds fetched, posts read), so a callback
        that fails must not take the collection down with it.
        """
        if on_stage is None:
            return
        try:
            on_stage(name, note, done, total)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"Progress callback failed at {name}: {exc}")

    def deep_dossier(self, platform: str, username: str, 
                     include_comments: bool = True,
                     include_transcripts: bool = True,
                     max_content_items: int = 50,
                     max_comments_per_item: int = 30,
                     on_stage=None) -> Dict[str, Any]:
        """
        Perform a comprehensive deep dossier collection.
        Collects: Everything available (2-5 minutes)
        
        Args:
            platform: Platform identifier
            username: Username/handle on the platform
            include_comments: Whether to fetch comments on content
            include_transcripts: Whether to fetch video transcripts
            max_content_items: Maximum content items to collect
            max_comments_per_item: Maximum comments per content item
            
        Returns:
            Comprehensive dossier with all available data
        """
        self.collection_start_time = time.time()
        logger.info(f"Starting DEEP DOSSIER for {username} on {platform}")
        
        result = {
            'collection_mode': 'deep_dossier',
            'platform': platform,
            'username': username,
            'collected_at': datetime.utcnow().isoformat(),
            'profile': None,
            'demographics': None,
            'content': [],
            'comments_analysis': {
                'total_comments_collected': 0,
                'sample_comments': [],
            },
            'transcripts': [],
            'social_graph': {
                'followers_sample': [],
                'following_sample': [],
            },
            'additional_data': {},
            'connected_accounts': [],
            'cross_platform_discovery': {},
            'statistics': {
                'api_calls_made': 0,
                'content_items_collected': 0,
                'comments_collected': 0,
                'transcripts_collected': 0,
            },
            'errors': [],
            'collection_time_seconds': 0,
        }
        
        if platform not in self.SUPPORTED_PLATFORMS:
            result['errors'].append(f"Unsupported platform: {platform}")
            return result
            
        config = self.SUPPORTED_PLATFORMS[platform]
        api_calls = 0
        self._stage(on_stage, 'profile', f'fetching the profile for {username}')
        
        # 1. Get profile
        try:
            profile_method = getattr(self.client, config['profile_method'], None)
            if profile_method:
                result['profile'] = profile_method(username)
                api_calls += 1
                logger.info(f"Profile collected for {username}")
        except Exception as e:
            # Facebook + ScrapeCreators credits exhausted -> Apify fallback
            # (skips Smart Resolution, which would also burn ScrapeCreators credits)
            if platform == 'facebook' and 'CREDITS_EXHAUSTED' in str(e):
                logger.warning(f"ScrapeCreators credits exhausted for {username}; trying Apify Facebook fallback...")
                if self._apify_facebook_fallback(username, result):
                    result['errors'].append('ScrapeCreators credits exhausted; served via Apify fallback')
                    api_calls += 1
                    # Skip ScrapeCreators deep methods/comments/cross-platform (all would fail)
                    return self._finalize_dossier(result, api_calls)
                result['errors'].append(f"Profile error (credits exhausted, Apify fallback failed): {str(e)}")
                return self._finalize_dossier(result, api_calls)
            # Smart Resolution for "Profile Not Found"
            logger.warning(f"Direct profile fetch failed for {username} on {platform}: {e}. Attempting Smart Resolution...")
            
            resolved_profile = self._smart_resolve_identity(platform, username)
            if resolved_profile:
                logger.info(f"Smart Resolution found match: {resolved_profile.get('username')}")
                
                result['profile'] = resolved_profile
                
                # CRITICAL: Update username/ID for subsequent deep calls
                # Prefer ID for YouTube/TikTok if available
                new_id = resolved_profile.get('id')
                new_username = resolved_profile.get('username')
                
                if platform == 'youtube' and new_id:
                     username = new_id # Use Channel ID
                     logger.info(f"Switched identity to Channel ID: {username}")
                elif new_username:
                     username = new_username
                     
                result['username'] = username
                api_calls += 1 # Count search as 1 call
                logger.info(f"Profile constructed via Smart Resolution for {username}")
            else:
                result['errors'].append(f"Profile error: {str(e)}")
        
        # 2. Execute all deep methods
        feeds = config.get('deep_methods', [])
        self._stage(on_stage, 'feeds', f"profile collected; reading {len(feeds)} feeds", 0, len(feeds))
        for feed_index, (data_key, method_name, params) in enumerate(feeds, start=1):
            try:
                method = getattr(self.client, method_name, None)
                if method:
                    # Add username to params if needed
                    call_params = {**params}
                    if 'channel_id' in method_name:
                        # YouTube needs channel_id from profile
                        if result['profile']:
                            call_params['channel_id'] = result['profile'].get('id', username)
                    else:
                        call_params['username'] = username
                    
                    # Make the call (handle different param styles)
                    if 'username' in call_params:
                        data = method(call_params.pop('username'), **call_params)
                    elif 'channel_id' in call_params:
                        data = method(call_params.pop('channel_id'), **call_params)
                    else:
                        data = method(username)
                    
                    # Store based on data type
                    if data_key in ['followers_sample', 'following_sample']:
                        result['social_graph'][data_key] = data
                    elif data_key == 'demographics':
                        result['demographics'] = data
                    elif data_key in ['videos', 'posts', 'reels', 'tweets', 'shorts']:
                        # Collect first, dedupe afterwards: the posts and reels
                        # feeds overlap, and truncating per call would let
                        # duplicates occupy slots that unique items should fill.
                        if isinstance(data, list):
                            result['content'].extend(data)
                    else:
                        result['additional_data'][data_key] = data
                    
                    api_calls += 1
                    logger.info(f"Collected {data_key} for {username}")
            except Exception as e:
                result['errors'].append(f"{data_key} error: {str(e)}")
                logger.warning(f"Failed to get {data_key} for {username}: {e}")
            self._stage(
                on_stage, 'feeds',
                f"read {feed_index} of {len(feeds)} feeds ({len(result['content'])} posts so far)",
                feed_index, len(feeds),
            )
        
        # Merge the per-endpoint feeds into one unique set before anything is
        # measured or paid for again (comments, transcripts).
        if result['content']:
            before = len(result['content'])
            result['content'], duplicates = dedupe_content(result['content'])
            result['statistics']['duplicate_items_removed'] = duplicates
            if duplicates:
                logger.info(f"Dropped {duplicates} duplicate content item(s) across feeds "
                            f"({before} -> {len(result['content'])})")
            result['content'] = result['content'][:max_content_items]

        # 3. Get comments on content items
        if include_comments and config.get('comments_method') and result['content']:
            comments_method = getattr(self.client, config['comments_method'], None)
            if comments_method:
                commented = set()
                comment_targets = result['content'][:10]  # Limit to first 10 items
                self._stage(on_stage, 'comments', f"reading comments on {len(comment_targets)} posts", 0, len(comment_targets))
                for read_index, item in enumerate(comment_targets, start=1):
                    try:
                        item_id = item.get('id') or item.get('video_id') or item.get('post_id')
                        # Never pay twice for the same post, even if it reached
                        # the content list under two different id formats.
                        if item_id and content_key(item) in commented:
                            continue
                        if item_id:
                            commented.add(content_key(item))
                            comments = comments_method(item_id, count=max_comments_per_item)
                            result['comments_analysis']['sample_comments'].extend(comments[:10])
                            result['comments_analysis']['total_comments_collected'] += len(comments)
                            api_calls += 1
                    except Exception as e:
                        logger.warning(f"Failed to get comments for item: {e}")
                    self._stage(
                        on_stage, 'comments',
                        f"read comments on {read_index} of {len(comment_targets)} posts "
                        f"({result['comments_analysis']['total_comments_collected']} comments)",
                        read_index, len(comment_targets),
                    )
        
        # 4. Get transcripts for video content
        if include_transcripts and config.get('transcript_method') and result['content']:
            transcript_method = getattr(self.client, config['transcript_method'], None)
            if transcript_method:
                transcript_targets = result['content'][:5]  # Limit to first 5 items
                self._stage(on_stage, 'transcripts', f"reading transcripts of {len(transcript_targets)} videos", 0, len(transcript_targets))
                for read_index, item in enumerate(transcript_targets, start=1):
                    try:
                        item_id = item.get('id') or item.get('video_id')
                        if item_id:
                            transcript = transcript_method(item_id)
                            if transcript and transcript.get('transcript'):
                                result['transcripts'].append({
                                    'item_id': item_id,
                                    'transcript': transcript
                                })
                                api_calls += 1
                    except Exception as e:
                        logger.warning(f"Failed to get transcript for item: {e}")
                    self._stage(
                        on_stage, 'transcripts',
                        f"read transcript {read_index} of {len(transcript_targets)}",
                        read_index, len(transcript_targets),
                    )
        
        # 5. Age/Gender prediction from profile image
        self._stage(on_stage, 'enrichment', 'predicting demographics and looking for other accounts')
        try:
            profile_image = None
            if result['profile']:
                profile_image = (
                    result['profile'].get('profile_image_url') or
                    result['profile'].get('avatar_url') or
                    result['profile'].get('avatar')
                )
            
            if profile_image:
                age_gender = self.client.get_age_and_gender(profile_image)
                result['demographics'] = result.get('demographics') or {}
                result['demographics']['predicted_age'] = age_gender.get('age')
                result['demographics']['predicted_gender'] = age_gender.get('gender')
                api_calls += 1
        except Exception as e:
            logger.warning(f"Failed to predict age/gender: {e}")
        
        # 6. Cross-Platform Discovery
        try:
            discovery_result = self.cross_platform_discovery(username, known_platforms=[platform])
            result['cross_platform_discovery'] = discovery_result
            
            # flatten discovered accounts for easy access
            discovered = []
            for plat, data in discovery_result.get('discovered_accounts', {}).items():
                if data.get('found'):
                    profile = data.get('profile', {})
                    discovered.append({
                        'platform': plat,
                        'username': profile.get('username'),
                        'url': profile.get('url') or profile.get('profile_url'),
                        'confidence': data.get('confidence')
                    })
            result['connected_accounts'] = discovered
            api_calls += len(discovered) # approximate
            logger.info(f"Discovered {len(discovered)} cross-platform accounts")
        except Exception as e:
            logger.warning(f"Cross-platform discovery failed: {e}")
        
        # Update statistics
        result['statistics']['api_calls_made'] = api_calls
        result['statistics']['content_items_collected'] = len(result['content'])
        result['statistics']['comments_collected'] = result['comments_analysis']['total_comments_collected']
        result['statistics']['transcripts_collected'] = len(result['transcripts'])
        result['collection_time_seconds'] = round(time.time() - self.collection_start_time, 2)
        
        logger.info(f"Deep dossier completed in {result['collection_time_seconds']}s with {api_calls} API calls")
        self._stage(
            on_stage, 'collected',
            f"collected {len(result['content'])} posts and "
            f"{result['comments_analysis']['total_comments_collected']} comments "
            f"in {api_calls} calls",
        )
        
        return result
    
    def cross_platform_discovery(self, username: str, 
                                  known_platforms: List[str] = None,
                                  check_all: bool = False) -> Dict[str, Any]:
        """
        Discover linked accounts across platforms.
        
        Args:
            username: Username to search for
            known_platforms: List of platforms where account is confirmed
            check_all: Whether to check all supported platforms
            
        Returns:
            Dict with discovered accounts and confidence scores
        """
        logger.info(f"Starting cross-platform discovery for {username}")
        
        result = {
            'search_username': username,
            'discovered_accounts': {},
            'potential_matches': [],
            'link_bio_accounts': [],
            'collection_time_seconds': 0,
        }
        
        start_time = time.time()
        
        # Platforms to check
        platforms_to_check = known_platforms or (
            list(self.SUPPORTED_PLATFORMS.keys()) if check_all 
            else ['tiktok', 'instagram', 'twitter', 'youtube', 'threads', 'linktree']
        )
        
        # 1. Check each platform for the username
        for platform in platforms_to_check:
            if platform not in self.SUPPORTED_PLATFORMS:
                continue
                
            config = self.SUPPORTED_PLATFORMS[platform]
            
            try:
                profile_method = getattr(self.client, config['profile_method'], None)
                if profile_method:
                    profile = profile_method(username)
                    if profile and profile.get('username'):
                        result['discovered_accounts'][platform] = {
                            'found': True,
                            'profile': profile,
                            'confidence': 1.0 if profile.get('username', '').lower() == username.lower() else 0.8
                        }
                        logger.info(f"Found {username} on {platform}")
            except ScrapeCreatorsError:
                result['discovered_accounts'][platform] = {
                    'found': False,
                    'profile': None,
                    'confidence': 0.0
                }
            except Exception as e:
                logger.warning(f"Error checking {platform}: {e}")
        
        # 2. Check link-in-bio platforms for additional links
        link_bio_platforms = ['linktree', 'komi', 'pillar', 'linkbio']
        for platform in link_bio_platforms:
            if platform in result['discovered_accounts'] and result['discovered_accounts'][platform]['found']:
                profile = result['discovered_accounts'][platform]['profile']
                # Extract links from raw data
                raw = profile.get('raw', {})
                links = raw.get('links', [])
                result['link_bio_accounts'].extend(links)
        
        # 3. Extract social links from bios
        for platform, data in result['discovered_accounts'].items():
            if data['found'] and data['profile']:
                bio = data['profile'].get('bio', '') or data['profile'].get('description', '')
                # Simple extraction - could be enhanced with regex
                if bio:
                    for check_platform in ['instagram', 'twitter', 'tiktok', 'youtube', 'twitch']:
                        if check_platform in bio.lower() and check_platform not in result['discovered_accounts']:
                            result['potential_matches'].append({
                                'platform': check_platform,
                                'source': f"{platform} bio",
                                'hint': bio[:100]
                            })
        
        result['collection_time_seconds'] = round(time.time() - start_time, 2)
        return result
    
    def collect_entire_footprint(self, usernames: Dict[str, str], 
                                  mode: str = 'deep') -> Dict[str, Any]:
        """
        Collect data from multiple platforms with different usernames.
        
        Args:
            usernames: Dict mapping platform to username
                       e.g., {'tiktok': 'user123', 'instagram': 'user_ig'}
            mode: 'quick' or 'deep'
            
        Returns:
            Combined dossier from all platforms
        """
        logger.info(f"Collecting entire digital footprint across {len(usernames)} platforms")
        start_time = time.time()
        
        result = {
            'collection_mode': f'multi_platform_{mode}',
            'platforms_requested': list(usernames.keys()),
            'platforms_collected': [],
            'platforms_failed': [],
            'dossiers': {},
            'unified_profile': {
                'display_names': [],
                'bios': [],
                'total_followers': 0,
                'total_posts': 0,
                'verified_anywhere': False,
            },
            'collection_time_seconds': 0,
        }
        
        # Collect from each platform
        for platform, username in usernames.items():
            try:
                if mode == 'quick':
                    dossier = self.quick_scan(platform, username)
                else:
                    dossier = self.deep_dossier(platform, username)
                
                result['dossiers'][platform] = dossier
                result['platforms_collected'].append(platform)
                
                # Aggregate into unified profile
                if dossier.get('profile'):
                    profile = dossier['profile']
                    if profile.get('display_name'):
                        result['unified_profile']['display_names'].append({
                            'platform': platform,
                            'name': profile['display_name']
                        })
                    if profile.get('bio'):
                        result['unified_profile']['bios'].append({
                            'platform': platform,
                            'bio': profile['bio']
                        })
                    result['unified_profile']['total_followers'] += (
                        profile.get('followers_count') or 
                        profile.get('follower_count') or 
                        profile.get('subscribers_count') or 0
                    )
                    result['unified_profile']['total_posts'] += (
                        profile.get('posts_count') or 
                        profile.get('video_count') or 
                        profile.get('media_count') or 0
                    )
                    if profile.get('verified'):
                        result['unified_profile']['verified_anywhere'] = True
                        
            except Exception as e:
                result['platforms_failed'].append({
                    'platform': platform,
                    'error': str(e)
                })
                logger.error(f"Failed to collect from {platform}: {e}")
        
        result['collection_time_seconds'] = round(time.time() - start_time, 2)
        logger.info(f"Multi-platform collection completed in {result['collection_time_seconds']}s")
        
        return result

    def _smart_resolve_identity(self, platform: str, query: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to resolve a username to a profile dict via search.
        Returns a normalized profile object if found.
        """
        try:
            if platform == 'youtube':
                # Search for channels first, then videos
                search_res = self.client.search_youtube(query, count=1)
                
                # Check Channels
                channels = search_res.get('channels', [])
                if channels:
                    c = channels[0]
                    return {
                        'id': c.get('id'),
                        'username': c.get('handle', '').replace('@', '') or c.get('channelName'),
                        'display_name': c.get('channelName'),
                        'bio': c.get('description'),
                        'followers_count': c.get('subscriberCountInt', 0),
                        'following_count': 0,
                        'posts_count': c.get('videoCountInt', 0), # Often not present in search but that's fine
                        'profile_image_url': c.get('thumbnail'),
                        'platform': 'youtube',
                        'verified': True,
                        'raw': c
                    }
                    
                # Check Videos (fallback)
                videos = search_res.get('videos', [])
                if videos:
                    v = videos[0]
                    c = v.get('channel', {})
                    if c.get('id'):
                        return {
                            'id': c.get('id'),
                            'username': c.get('handle', '').replace('@', '') or c.get('title'),
                            'display_name': c.get('title'),
                            'bio': '',
                            'followers_count': 0, # Not in video obj
                            'following_count': 0,
                            'posts_count': 0,
                            'profile_image_url': c.get('thumbnail'),
                            'platform': 'youtube',
                            'verified': False,
                            'raw': c
                        }

        except Exception as e:
            logger.warning(f"Smart resolution failed for {query} on {platform}: {e}")
        
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# PLATFORM-SPECIFIC DEEP COLLECTORS
# ═══════════════════════════════════════════════════════════════════════════════

class TikTokDeepCollector:
    """Specialized collector for comprehensive TikTok intelligence"""
    
    def __init__(self, client: ScrapeCreatorsClient):
        self.client = client
    
    def collect_all(self, username: str, include_shop: bool = True) -> Dict[str, Any]:
        """Collect all available TikTok data"""
        result = {
            'platform': 'tiktok',
            'username': username,
            'profile': None,
            'demographics': None,
            'videos': [],
            'video_transcripts': [],
            'video_comments': [],
            'followers_sample': [],
            'following_sample': [],
            'live_status': None,
            'shop_products': [],
            'errors': [],
        }
        
        # Profile
        try:
            result['profile'] = self.client.get_tiktok_profile(username)
        except Exception as e:
            result['errors'].append(f"Profile: {e}")
        
        # Demographics
        try:
            result['demographics'] = self.client.get_tiktok_audience_demographics(username)
        except Exception as e:
            result['errors'].append(f"Demographics: {e}")
        
        # Videos
        try:
            result['videos'] = self.client.get_tiktok_videos(username, count=50)
        except Exception as e:
            result['errors'].append(f"Videos: {e}")
        
        # Transcripts for top videos
        for video in result['videos'][:5]:
            try:
                video_id = video.get('id')
                if video_id:
                    transcript = self.client.get_tiktok_transcript(video_id)
                    if transcript:
                        result['video_transcripts'].append({
                            'video_id': video_id,
                            'transcript': transcript
                        })
            except Exception:
                pass
        
        # Comments on top videos
        for video in result['videos'][:10]:
            try:
                video_id = video.get('id')
                if video_id:
                    comments = self.client.get_tiktok_comments(video_id, count=50)
                    result['video_comments'].extend(comments)
            except Exception:
                pass
        
        # Social graph samples
        try:
            result['followers_sample'] = self.client.get_tiktok_followers(username, count=100)
        except Exception as e:
            result['errors'].append(f"Followers: {e}")
            
        try:
            result['following_sample'] = self.client.get_tiktok_following(username, count=100)
        except Exception as e:
            result['errors'].append(f"Following: {e}")
        
        # Live status
        try:
            result['live_status'] = self.client.get_tiktok_live(username)
        except Exception as e:
            result['errors'].append(f"Live: {e}")
        
        # TikTok Shop (if enabled)
        if include_shop:
            try:
                result['shop_products'] = self.client.get_tiktok_shop_products(username, count=50)
            except Exception as e:
                result['errors'].append(f"Shop: {e}")
        
        return result


class InstagramDeepCollector:
    """Specialized collector for comprehensive Instagram intelligence"""
    
    def __init__(self, client: ScrapeCreatorsClient):
        self.client = client
    
    def collect_all(self, username: str) -> Dict[str, Any]:
        """Collect all available Instagram data"""
        result = {
            'platform': 'instagram',
            'username': username,
            'profile': None,
            'posts': [],
            'reels': [],
            'highlights': [],
            'highlight_details': [],
            'post_comments': [],
            'reel_transcripts': [],
            'errors': [],
        }
        
        # Profile
        try:
            result['profile'] = self.client.get_instagram_profile(username)
        except Exception as e:
            result['errors'].append(f"Profile: {e}")
        
        # Posts
        try:
            result['posts'] = self.client.get_instagram_posts_deep(username, count=30)
        except Exception as e:
            result['errors'].append(f"Posts: {e}")
        
        # Reels
        try:
            result['reels'] = self.client.get_instagram_reels(username, count=30)
        except Exception as e:
            result['errors'].append(f"Reels: {e}")
        
        # Highlights
        try:
            result['highlights'] = self.client.get_instagram_story_highlights(username)
            # Get details for each highlight
            for highlight in result['highlights'][:5]:
                highlight_id = highlight.get('id')
                if highlight_id:
                    details = self.client.get_instagram_highlight_details(highlight_id)
                    result['highlight_details'].append(details)
        except Exception as e:
            result['errors'].append(f"Highlights: {e}")
        
        # Comments on top posts
        for post in result['posts'][:10]:
            try:
                post_id = post.get('id')
                if post_id:
                    comments = self.client.get_instagram_comments(post_id, count=50)
                    result['post_comments'].extend(comments)
            except Exception:
                pass
        
        # Transcripts for reels
        for reel in result['reels'][:5]:
            try:
                reel_id = reel.get('id')
                if reel_id:
                    transcript = self.client.get_instagram_transcript(reel_id)
                    if transcript:
                        result['reel_transcripts'].append({
                            'reel_id': reel_id,
                            'transcript': transcript
                        })
            except Exception:
                pass
        
        return result


class YouTubeDeepCollector:
    """Specialized collector for comprehensive YouTube intelligence"""
    
    def __init__(self, client: ScrapeCreatorsClient):
        self.client = client
    
    def collect_all(self, channel_id: str) -> Dict[str, Any]:
        """Collect all available YouTube data"""
        result = {
            'platform': 'youtube',
            'channel_id': channel_id,
            'channel_details': None,
            'videos': [],
            'shorts': [],
            'video_transcripts': [],
            'video_comments': [],
            'community_posts': [],
            'playlists': [],
            'errors': [],
        }
        
        # Channel details
        try:
            result['channel_details'] = self.client.get_youtube_channel_details(channel_id)
        except Exception as e:
            result['errors'].append(f"Channel: {e}")
        
        # Videos
        try:
            result['videos'] = self.client.get_youtube_videos_deep(channel_id, count=50)
        except Exception as e:
            result['errors'].append(f"Videos: {e}")
        
        # Shorts
        try:
            result['shorts'] = self.client.get_youtube_channel_shorts(channel_id, count=30)
        except Exception as e:
            result['errors'].append(f"Shorts: {e}")
        
        # Transcripts for top videos
        for video in result['videos'][:10]:
            try:
                video_id = video.get('id') or video.get('video_id')
                if video_id:
                    transcript = self.client.get_youtube_transcript(video_id)
                    if transcript and transcript.get('transcript'):
                        result['video_transcripts'].append({
                            'video_id': video_id,
                            'transcript': transcript
                        })
            except Exception:
                pass
        
        # Comments on top videos
        for video in result['videos'][:5]:
            try:
                video_id = video.get('id') or video.get('video_id')
                if video_id:
                    comments = self.client.get_youtube_comments(video_id, count=100)
                    result['video_comments'].extend(comments)
            except Exception:
                pass
        
        return result


# Convenience function
def create_deep_collector(client: ScrapeCreatorsClient = None) -> DeepDossierCollector:
    """Create and return a DeepDossierCollector instance"""
    return DeepDossierCollector(client)
