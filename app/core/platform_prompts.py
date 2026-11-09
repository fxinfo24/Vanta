"""
Vanta: Platform-Specific AI Prompts
Optimized Grok 4.1 prompts for each platform's unique characteristics
"""

import re
from typing import Dict, Any, List, Optional

from app.utils.helpers import identity_description


# ---------------------------------------------------------------------------
# Data availability
# ---------------------------------------------------------------------------
# Dossiers differ by provider: a deep Facebook item carries `reactionCount`,
# `share_count`, `commentCount`, `videoDetails` and `/reel/` URLs, while a thin
# item carries none of those. Hardcoding "we have no engagement/media data" for
# a platform therefore told the model to ignore data it had been given, and "no
# engagement" leaks out as "zero engagement". Availability is computed from the
# samples and both prompts render it verbatim.

_ENGAGEMENT_KEYS = (
    "reactionCount", "reaction_count", "share_count", "shares",
    "commentCount", "comment_count", "videoViewCount", "view_count",
    "like_count", "likes", "reactions",
)

# Minimum number of comment authors carrying a stated gender before audience
# composition may be described at all (n=4 must never become "100% male").
MIN_DEMOGRAPHIC_SAMPLE = 10


def _content_availability(content_items: Optional[List[Any]], profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """Describe what the collected samples actually contain."""
    items = [i for i in (content_items or []) if isinstance(i, dict)]
    avail: Dict[str, Any] = {
        "n_items": len(items),
        "engagement_items": 0,
        "reactions": 0,
        "shares": 0,
        "comments": 0,
        "median_reactions": 0,
        "video_items": 0,
        "image_items": 0,
        "gendered_commenters": 0,
        "has_network": False,
        "has_groups": False,
        "has_profile_image": bool(profile_data.get("profile_image_url")),
    }

    reactions = []
    for item in items:
        if any(item.get(k) is not None for k in _ENGAGEMENT_KEYS):
            avail["engagement_items"] += 1
            reactions_count = item.get("reactionCount", item.get("reaction_count"))
            if reactions_count is None:
                reactions_count = item.get("likes", item.get("reactions"))
            if isinstance(reactions_count, int):
                reactions.append(reactions_count)
            avail["reactions"] += int(item.get("reactionCount", item.get("reaction_count")) or 0)
            avail["shares"] += int(item.get("share_count", item.get("shares")) or 0)
            avail["comments"] += int(item.get("commentCount", item.get("comment_count")) or 0)

        url = item.get("url") or item.get("permalink") or ""
        is_video = (
            bool(item.get("videoDetails")) or "/reel/" in url or "/watch" in url
            or "/videos/" in url or str(item.get("media_type") or "").lower() == "video"
        )
        if is_video:
            avail["video_items"] += 1
        elif item.get("image") or item.get("images"):
            avail["image_items"] += 1

        for comment in item.get("topComments") or []:
            author = (comment or {}).get("author") or {}
            if author.get("gender"):
                avail["gendered_commenters"] += 1

    if reactions:
        from statistics import median
        avail["median_reactions"] = median(reactions)

    avail["has_engagement"] = avail["engagement_items"] > 0
    avail["has_media"] = (avail["video_items"] + avail["image_items"]) > 0
    avail["has_demographics"] = avail["gendered_commenters"] >= MIN_DEMOGRAPHIC_SAMPLE
    avail["has_network"] = bool(
        profile_data.get("followers_sample") or profile_data.get("following_sample")
    )
    avail["has_groups"] = bool(profile_data.get("groups"))
    return avail


def _normalize_quote(value: Any) -> str:
    """Case/whitespace-insensitive form used to prove a quote is verbatim."""
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


# Short fragments match too easily to prove anything.
MIN_RECEIPT_QUOTE_CHARS = 10


def verify_claim_evidence(payload: Any, content_items: Optional[List[Any]],
                          section: str = "this section") -> Any:
    """Drop receipts that are not literal text from the collected posts.

    Prompts ask for ``evidence: [{claim, quote}]``. A paraphrased quote is the
    same defect as an invented one, so each quote must appear verbatim in the
    samples. Survivors are kept; the count of removals is stated in
    ``limitations`` so the user knows the section lost support.
    """
    if not isinstance(payload, dict) or "error" in payload:
        return payload
    raw = payload.get("evidence")
    if not raw:
        return payload

    corpus = "\n".join(
        _normalize_quote(item.get("text") or item.get("content") or "")
        for item in (content_items or []) if isinstance(item, dict)
    )

    entries = []
    if isinstance(raw, dict):
        entries = [{"claim": k, "quote": v} for k, v in raw.items()]
    elif isinstance(raw, list):
        entries = [e for e in raw if isinstance(e, dict)]

    kept, rejected = [], 0
    for entry in entries:
        quote = _normalize_quote(entry.get("quote"))
        if len(quote) >= MIN_RECEIPT_QUOTE_CHARS and corpus and quote in corpus:
            kept.append({"claim": str(entry.get("claim") or "").strip(), "quote": entry.get("quote")})
        else:
            rejected += 1

    payload["evidence"] = kept
    payload["evidence_verified"] = len(kept)
    if rejected:
        payload["evidence_rejected"] = rejected
        limitations = payload.get("limitations")
        if not isinstance(limitations, list):
            limitations = [limitations] if limitations else []
        limitations.append(
            f"{rejected} receipt(s) for {section} were rejected because the quoted text "
            "does not appear in the collected posts."
        )
        payload["limitations"] = limitations
    return payload


def _boundary_text(avail: Dict[str, Any]) -> str:
    """Render DATA BOUNDARIES from the data actually present."""
    lines = ["DATA BOUNDARIES - grounds every claim you may make:"]

    if avail["has_engagement"]:
        lines.append(
            f"- ENGAGEMENT: collected for {avail['engagement_items']} of {avail['n_items']} items "
            f"(total {avail['reactions']} reactions, {avail['shares']} shares, "
            f"{avail['comments']} comments; median {avail['median_reactions']} reactions/item). "
            "You MAY quantify engagement using exactly these numbers - nothing wider."
        )
    else:
        lines.append(
            "- ENGAGEMENT: no reaction/share/comment metrics were collected. Do NOT state "
            "engagement levels, 'near-zero engagement', reach or shadow suppression."
        )

    if avail["has_media"]:
        lines.append(
            f"- MEDIA: {avail['video_items']} video/reel item(s) and {avail['image_items']} "
            "image item(s) were collected. Do NOT claim the account posts no video or no images."
        )
    else:
        lines.append(
            "- MEDIA: no media-type metadata was collected. Absence in samples is NOT evidence "
            "of absence on the account - do not state 'no video/Reels', 'zero multimedia' or "
            "'live streams unused' as fact."
        )

    if avail["has_demographics"]:
        lines.append(
            f"- AUDIENCE: gender is stated for {avail['gendered_commenters']} comment authors. "
            "You MAY describe that sample, stating its size."
        )
    else:
        lines.append(
            f"- AUDIENCE: only {avail['gendered_commenters']} comment author(s) carry demographic "
            f"data (minimum for any composition claim is {MIN_DEMOGRAPHIC_SAMPLE}). Do NOT "
            "generalize audience gender, age or location ('male-dominated', 'educated urban')."
        )

    if not avail["has_network"]:
        lines.append(
            "- NETWORK: no follower/following lists were collected. Do NOT claim coordinated "
            "behavior, bot networks, follow-for-follow or purchased followers - and do not raise "
            "risk merely because of the account's topical niche."
        )
    if not avail["has_groups"]:
        lines.append("- GROUPS: no group membership data was collected. Never claim group absence or presence.")

    return "\n".join(lines)

# Platform-specific context and terminology
PLATFORM_CONTEXTS = {
    # === Social Platforms ===
    "twitter": {
        "name": "Twitter/X",
        "content_type": "tweets",
        "key_metrics": ["retweets", "likes", "replies", "quotes", "impressions"],
        "engagement_factors": ["viral potential", "ratio (replies/likes)", "quote tweet sentiment"],
        "authenticity_signals": ["blue check", "follower/following ratio", "account age vs activity"],
        "cultural_context": """Twitter/X is a real-time microblogging platform focused on news, opinions, and 
        public discourse. Content is limited to 280 characters (premium: longer). Key behaviors include:
        - High engagement on trending topics and hot takes
        - Thread culture for extended thoughts
        - Quote tweets for commentary
        - Ratio culture (many replies with few likes = controversial)
        - Influence measured by virality and discourse impact"""
    },
    
    "instagram": {
        "name": "Instagram",
        "content_type": "posts/reels/stories",
        "key_metrics": ["likes", "comments", "saves", "shares", "reach", "story views"],
        "engagement_factors": ["aesthetic quality", "hashtag performance", "reel virality"],
        "authenticity_signals": ["engagement rate vs followers", "comment quality", "follower demographics"],
        "cultural_context": """Instagram is a visual-first platform emphasizing aesthetics and lifestyle. Key behaviors:
        - High-quality imagery and video is essential
        - Reels now drive maximum reach
        - Stories for real-time, ephemeral content
        - Influencer economy is highly developed
        - Engagement rate of 3-6% is considered healthy
        - Fake followers and engagement pods are common issues"""
    },
    
    "tiktok": {
        "name": "TikTok",
        "content_type": "videos",
        "key_metrics": ["views", "likes", "comments", "shares", "saves", "FYP appearances"],
        "engagement_factors": ["watch time", "completion rate", "sound usage", "trend participation"],
        "authenticity_signals": ["consistent posting", "niche focus", "organic growth pattern"],
        "cultural_context": """TikTok is an algorithm-driven short-video platform. Key behaviors:
        - For You Page (FYP) is the primary discovery mechanism
        - Sound/music trends drive viral content
        - Duets and stitches for collaboration
        - Creator Fund incentivizes engagement farming
        - Authenticity and relatability outperform polish
        - Growth can be explosive but also volatile"""
    },
    
    "youtube": {
        "name": "YouTube",
        "content_type": "videos/shorts",
        "key_metrics": ["views", "watch time", "subscribers", "likes", "comments", "CTR"],
        "engagement_factors": ["thumbnail CTR", "average view duration", "subscriber conversion"],
        "authenticity_signals": ["sub/view ratio", "comment sentiment", "consistent upload schedule"],
        "cultural_context": """YouTube is the dominant long-form video platform. Key behaviors:
        - SEO and thumbnails drive discovery
        - Watch time is the key algorithm signal
        - Shorts now compete with TikTok
        - Monetization requires 1K subs + 4K watch hours
        - Comment section community building matters
        - Channel consistency builds loyal audiences"""
    },
    
    "linkedin": {
        "name": "LinkedIn",
        "content_type": "posts/articles",
        "key_metrics": ["impressions", "reactions", "comments", "shares", "profile views"],
        "engagement_factors": ["professional relevance", "thought leadership", "network reach"],
        "authenticity_signals": ["work history verification", "endorsements", "recommendation quality"],
        "cultural_context": """LinkedIn is the professional networking platform. Key behaviors:
        - B2B and career-focused content performs best
        - Algorithm favors native content over links
        - Engagement within first hour is critical
        - Personal stories with professional lessons go viral
        - Cringe culture: overly salesy or humble-brag posts
        - Thought leadership builds influence"""
    },
    
    "facebook": {
        "name": "Facebook",
        "content_type": "posts/reels/stories",
        "key_metrics": ["reactions", "comments", "shares", "reach", "group engagement"],
        "engagement_factors": ["share-worthiness", "group activity", "local relevance"],
        "authenticity_signals": ["friend count patterns", "timeline activity consistency", "group memberships"],
        "cultural_context": """Facebook is a mature, multi-generational social network. Key behaviors:
        - Groups are increasingly important for reach
        - Algorithm heavily suppresses organic reach
        - Video (especially live) gets priority
        - Older demographics dominate
        - Marketplace and local community features
        - Memory features drive engagement"""
    },
    
    "reddit": {
        "name": "Reddit",
        "content_type": "posts/comments",
        "key_metrics": ["upvotes", "comments", "awards", "karma"],
        "engagement_factors": ["subreddit fit", "timing", "title quality", "genuine contribution"],
        "authenticity_signals": ["karma-to-age ratio", "subreddit diversity", "comment vs post activity"],
        "cultural_context": """Reddit is a community-driven discussion platform. Key behaviors:
        - Subreddits have unique cultures and rules
        - Self-promotion is heavily policed
        - Authentic participation builds karma
        - AMA (Ask Me Anything) for visibility
        - Hivemind dynamics influence voting
        - Anonymous culture values substance over identity"""
    },
    
    # === Streaming Platforms ===
    "twitch": {
        "name": "Twitch",
        "content_type": "live streams/clips",
        "key_metrics": ["concurrent viewers", "followers", "subscribers", "chat activity", "raids"],
        "engagement_factors": ["stream consistency", "chat interaction", "community events"],
        "authenticity_signals": ["concurrent vs follower ratio", "sub retention", "organic raids"],
        "cultural_context": """Twitch is the dominant live streaming platform. Key behaviors:
        - Consistency and schedule are crucial
        - Chat culture defines community
        - Bits and subscriptions = monetization
        - Raids build community connections
        - Clip virality on other platforms drives growth
        - Variety vs niche streaming strategies"""
    },
    
    "kick": {
        "name": "Kick",
        "content_type": "live streams",
        "key_metrics": ["viewers", "followers", "chat activity", "tips"],
        "engagement_factors": ["creator revenue share", "less restrictive content policies"],
        "authenticity_signals": ["migration timing", "cross-platform presence", "audience transfer"],
        "cultural_context": """Kick is an emerging Twitch alternative. Key behaviors:
        - Higher creator revenue share (95/5 split)
        - Less strict content moderation
        - Gambling streams are more permitted
        - Many creators dual-stream
        - Growing but smaller audience base"""
    },
    
    # === Professional/Developer ===
    "github": {
        "name": "GitHub",
        "content_type": "repositories/contributions",
        "key_metrics": ["stars", "forks", "followers", "contributions", "PR activity"],
        "engagement_factors": ["code quality", "documentation", "community management"],
        "authenticity_signals": ["contribution graph consistency", "project diversity", "issue response time"],
        "cultural_context": """GitHub is the developer collaboration platform. Key behaviors:
        - Contribution graph shows activity patterns
        - Stars indicate project popularity
        - Open source involvement builds reputation
        - Profile README for personal branding
        - Sponsors program for monetization"""
    },
    
    # === Emerging Platforms ===
    "threads": {
        "name": "Threads",
        "content_type": "text posts",
        "key_metrics": ["likes", "replies", "reposts", "quotes"],
        "engagement_factors": ["Instagram cross-posting", "conversation starters"],
        "authenticity_signals": ["Instagram account linkage", "early adopter timing", "engagement patterns"],
        "cultural_context": """Threads is Meta's Twitter competitor. Key behaviors:
        - Tied to Instagram identity
        - Text-focused but supports images/video
        - Algorithm-driven feed (no chronological option)
        - Decentralization planned (ActivityPub)
        - Still defining its culture"""
    },
    
    "bluesky": {
        "name": "Bluesky",
        "content_type": "posts",
        "key_metrics": ["likes", "reposts", "replies", "followers"],
        "engagement_factors": ["algorithm-free chronological", "custom feeds", "invite-only dynamics"],
        "authenticity_signals": ["invite tree tracing", "early adopter status", "domain handles"],
        "cultural_context": """Bluesky is a decentralized Twitter alternative. Key behaviors:
        - AT Protocol (decentralized)
        - Custom domain handles for verification
        - Custom algorithmic feeds
        - Tech/media early adopter community
        - No ads (currently)
        - Strong moderation tools"""
    },
    
    # === Link Aggregators ===
    "linktree": {
        "name": "Linktree",
        "content_type": "link pages",
        "key_metrics": ["views", "clicks", "CTR", "subscriber signups"],
        "engagement_factors": ["link organization", "visual design", "call-to-action clarity"],
        "authenticity_signals": ["social proof integration", "verified badge", "analytics integration"],
        "cultural_context": """Linktree aggregates links for bio-limited platforms. Analysis focuses on:
        - Link diversity and categorization
        - Priority content signals
        - Monetization strategies
        - Cross-platform presence mapping"""
    },
    "google": {
        "name": "Google",
        "content_type": "search results/knowledge panel",
        "key_metrics": ["reviews", "rating", "search ranking", "knowledge panel presence", "photos"],
        "engagement_factors": ["review quality", "photo freshness", "info accuracy"],
        "authenticity_signals": ["verified business profile", "consistent NAP (Name, Address, Phone)", "review velocity"],
        "cultural_context": """Google My Business/Profile is the digital front door. Analysis focuses on:
        - Reputation management through reviews
        - Local SEO visibility
        - Brand authority signals (Knowledge Graph)
        - Visual proof through customer/business photos"""
    },

    "tiktok_shop": {
        "name": "TikTok Shop",
        "content_type": "product listings/shoppable videos",
        "key_metrics": ["sales", "conversion rate", "GMV", "affiliate engagement", "video attribution"],
        "engagement_factors": ["product appeal", "pricing strategy", "creator affiliate network"],
        "authenticity_signals": ["verified seller status", "shipping performance", "refund rates"],
        "cultural_context": """TikTok Shop is a social commerce ecosystem. Key behaviors:
        - Shoppable videos drive impulse buys
        - Affiliate creators are the main sales channel
        - Live shopping events create urgency
        - Viral product trends (TikTok Made Me Buy It)
        - Fast trends require rapid inventory adaptation"""
    },

    "amazon_shop": {
        "name": "Amazon Shop",
        "content_type": "storefront/product pages",
        "key_metrics": ["BSR (Best Seller Rank)", "reviews", "rating", "A+ content engagement", "conversion"],
        "engagement_factors": ["listing optimization", "image quality", "A+ content storytelling"],
        "authenticity_signals": ["brand registry", "review authenticity", "seller feedback"],
        "cultural_context": """Amazon Storefronts represent brand authority on the world's largest marketplace. behaviors:
        - Brand Registry builds trust
        - A+ Content tells the brand story
        - Store design dictates user journey
        - Search visibility drives traffic
        - Review social proof is paramount"""
    },
}

# Default context for platforms not specifically defined
DEFAULT_PLATFORM_CONTEXT = {
    "name": "Social Media Platform",
    "content_type": "posts",
    "key_metrics": ["followers", "likes", "comments", "shares"],
    "engagement_factors": ["content quality", "posting consistency", "audience interaction"],
    "authenticity_signals": ["account age", "engagement rate", "content originality"],
    "cultural_context": """General social media platform. Analysis will use universal metrics 
    and engagement patterns applicable across social platforms."""
}


def get_platform_context(platform: str) -> Dict[str, Any]:
    """Get platform-specific context for prompts"""
    return PLATFORM_CONTEXTS.get(platform.lower(), DEFAULT_PLATFORM_CONTEXT)


def build_content_analysis_prompt(platform: str, profile_data: Dict[str, Any], posts: list) -> str:
    """Build a platform-optimized content analysis prompt"""
    ctx = get_platform_context(platform)
    
    # Dossiers store 'follower_count' (singular); some clients use 'followers_count'.
    # Normalize so the real follower count reaches the model — a key mismatch
    # historically rendered as 0 and the model invented a "contradiction".
    profile_data = {
        **profile_data,
        "follower_count": profile_data.get("follower_count") or profile_data.get("followers_count"),
    }
    # following/posts are never exposed by some providers (e.g. ScrapeCreators
    # Facebook) — they arrive as 0 placeholders. Presenting them as real zeros
    # makes the model invent narratives, so render them as unknown instead.
    _num = lambda v: f"{v:,}" if v else "unknown (not exposed by provider)"
    _verified = profile_data.get('verified')
    _verified_str = 'Yes' if _verified else ('No' if _verified is False else 'unknown (not exposed by provider)')
    # Computed from the samples: never assert a data stream is absent when the
    # provider did return it (Facebook deep items carry reactions/media).
    boundaries = _boundary_text(_content_availability(posts, profile_data))
    profile_summary = f"""
Profile: @{profile_data.get('username', 'unknown')}
Name: {profile_data.get('display_name', 'N/A')}
Bio: {(profile_data.get('bio') or 'No bio')[:500]}
Followers: {_num(profile_data.get('follower_count'))}
Following: {_num(profile_data.get('following_count'))}
Content Count: {_num(profile_data.get('posts_count'))}
Verified: {_verified_str}
Platform: {ctx['name']}
{boundaries}
CRITICAL: Any metric marked 'unknown (not exposed by provider)' is MISSING data, not zero.
Never treat an unknown metric or a missing data stream as evidence. Ground every claim in the profile metrics and samples above.
""".strip()
    
    recent_content = "\n".join([
        f"[{i+1}] {str(post.get('content', post.get('text', '')))[:300]}"
        for i, post in enumerate(posts[:10])
    ])
    
    return f"""You are an expert {ctx['name']} analyst specializing in creator intelligence and social media forensics.

PLATFORM CONTEXT:
{ctx['cultural_context']}

KEY METRICS FOR {ctx['name'].upper()}: {', '.join(ctx['key_metrics'])}
ENGAGEMENT FACTORS: {', '.join(ctx['engagement_factors'])}

PROFILE DATA:
{profile_summary}

RECENT {ctx['content_type'].upper()}:
{recent_content}

Analyze this {ctx['name']} profile considering the platform's unique culture and metrics.
Provide comprehensive analysis in JSON format with these categories:

1. content_themes: Array of main content themes/topics (platform-specific terminology)
2. writing_style: Object with tone, formality, humor_level, emoji_usage, platform_literacy
3. personality_traits: Object with Big Five personality scores (0-1) inferred from content
4. posting_patterns: Object with frequency, timing, consistency insights
5. platform_fit: How well this creator leverages {ctx['name']}'s unique features (0-1)
6. audience_engagement: Object with engagement style and community interaction quality
7. authenticity_indicators: Object analyzing {', '.join(ctx['authenticity_signals'][:3])}
8. influence_factors: Object with authority indicators and thought leadership signals
9. sentiment_analysis: Object with overall emotional tone and positivity
10. growth_potential: Assessment of future growth on this platform (0-1)
11. key_insights: Array of 5 most important {ctx['name']}-specific observations
12. evidence: Array of receipts for the claims above
    - claim: the specific claim (e.g. "personality_traits.openness=0.85")
    - quote: EXACT text copied from RECENT {ctx['content_type'].upper()} - no paraphrase

EVIDENCE RULES: personality_traits and writing_style must each be backed by at least
one verbatim quote from the samples. Receipts that cannot be matched to the samples
are discarded, so an unbacked trait reads as unbacked rather than as a finding.

Use numerical scores (0-1) where applicable. Reference platform-specific behaviors."""


def build_authenticity_prompt(platform: str, profile_data: Dict[str, Any]) -> str:
    """Build a platform-optimized authenticity analysis prompt"""
    ctx = get_platform_context(platform)
    
    return f"""You are a cybersecurity expert specializing in fake account detection on {ctx['name']}.

PLATFORM-SPECIFIC AUTHENTICITY SIGNALS:
{', '.join(ctx['authenticity_signals'])}

PROFILE METRICS:
{identity_description(profile_data)}
Account Created: {profile_data.get('created_at', 'Unknown')}
Followers: {(lambda v: f'{v:,}' if v else 'unknown (not exposed by provider)')(profile_data.get('follower_count'))}
Following: {(lambda v: f'{v:,}' if v else 'unknown (not exposed by provider)')(profile_data.get('following_count'))}
{ctx['content_type'].title()} Count: {(lambda v: f'{v:,}' if v else 'unknown (not exposed by provider)')(profile_data.get('posts_count'))}
Verified: {profile_data.get('verified', False)}
Bio Length: {len(str(profile_data.get('bio', '')))} characters
Profile Image: {'Present' if profile_data.get('profile_image_url') else 'Missing'}

CRITICAL: Any metric marked 'unknown (not exposed by provider)' is MISSING data, not zero.
Never treat an unknown metric as evidence (e.g. do not infer purchased followers from an unknown
following count), and never claim group participation, multimedia usage, or demographic
composition when the data does not contain them.
DATA BOUNDARIES - this dataset contains NO media-type metadata, NO engagement metrics
(likes/shares/reactions), NO group membership data, and NO audience demographic breakdowns.
Absence of such data in samples is NOT evidence of absence on the account: do NOT state
'no video/Reels', 'zero multimedia', 'near-zero engagement', 'shadow suppression' or any
reach/engagement claim as a flag. State only what the metrics above actually show.

PLATFORM CONTEXT:
{ctx['cultural_context']}

Analyze authenticity considering {ctx['name']}'s specific bot/fake patterns.
Return JSON with:

1. overall_authenticity: score (0-1), confidence (0-1)
2. bot_likelihood: Score 0-1 for automated behavior probability
3. fake_follower_risk: Assessment of purchased followers/engagement
4. content_authenticity: Human vs AI-generated content likelihood
5. platform_specific_flags: {ctx['name']}-specific red flags
6. engagement_quality: Analysis of interaction authenticity
7. account_age_consistency: Age vs activity pattern analysis
8. red_flags: Array of concerning indicators
9. green_flags: Array of positive authenticity indicators
10. risk_assessment: "low" | "medium" | "high" | "critical"
11. confidence_notes: Explanation of confidence level"""


def build_prediction_prompt(platform: str, profile_data: Dict[str, Any], content_analysis: Dict[str, Any]) -> str:
    """Build a platform-optimized prediction prompt with CTB psychology"""
    ctx = get_platform_context(platform)
    
    return f"""You are a data scientist specializing in {ctx['name']} growth analytics, creator economy forecasting, 
and CTB (Click-To-Benefit) psychology - the art of leading with VALUE to drive engagement and conversions.

PLATFORM CONTEXT:
{ctx['cultural_context']}

CTB (CLICK-TO-BENEFIT) PSYCHOLOGY PRINCIPLES:
CTB is the opposite of pushy CTA tactics. It focuses on making the user WANT to engage because they see clear benefit:
- Value First: Lead with what the user GAINS, not what you want them to do
- Benefit Clarity: Make the advantage immediately obvious and compelling
- Trust Building: Demonstrate expertise before asking for anything
- Reciprocity: Give genuine value that creates natural desire to reciprocate
- Psychological Safety: Remove friction, fear, and uncertainty
- Identity Alignment: Connect to who the user wants to become
- Urgency Through FOMO on Value: Not scarcity tricks, but genuine "don't miss this benefit"

PROFILE: @{profile_data.get('username')}
CURRENT METRICS: {profile_data.get('follower_count', 0):,} followers, {profile_data.get('posts_count', 0):,} {ctx['content_type']}
CONTENT THEMES: {content_analysis.get('content_themes', [])}
PLATFORM FIT SCORE: {content_analysis.get('platform_fit', 'N/A')}

Generate {ctx['name']}-specific predictions with CTB psychology insights in JSON format:

1. growth_forecast: Object with 30/90/365 day follower predictions considering {ctx['name']}'s growth dynamics
2. content_evolution: Predicted changes in {ctx['content_type']} themes/style
3. engagement_trends: Expected changes in {', '.join(ctx['key_metrics'][:3])}
4. viral_potential: Likelihood of creating viral {ctx['content_type']} (0-1)
5. ctb_strengths: Array of CTB (value-first) tactics this creator already uses effectively
6. ctb_opportunities: Array of CTB improvements - how to lead with MORE benefit/value
7. value_proposition: Clear articulation of what benefit their audience receives
8. platform_expansion: Other platforms where this creator would succeed + psychological fit
9. optimal_strategy: Best {ctx['name']}-specific tactics using CTB (benefit-first) principles
10. audience_motivation: What benefits/value their audience is seeking
11. trust_indicators: Signals that build audience trust and credibility (0-1)
12. risk_factors: Platform-specific risks (algorithm changes, audience fatigue, etc.)
13. success_probability: Overall likelihood of continued growth (0-1)
14. actionable_insights: 5 specific {ctx['name']} recommendations using CTB psychology

Focus on VALUE delivery. What BENEFIT does this creator provide that makes people WANT to engage?"""


# Supported platforms list (without Truth Social)
SUPPORTED_PLATFORMS = [
    "twitter", "instagram", "tiktok", "youtube", "linkedin", "facebook",
    "reddit", "pinterest", "snapchat", "threads", "bluesky", "twitch",
    "kick", "github", "linktree", "komi", "pillar", "linkbio", "google",
    "tiktok_shop", "amazon_shop"
]
