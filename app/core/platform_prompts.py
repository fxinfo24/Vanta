"""
Vanta: Platform-Specific AI Prompts
Optimized Grok 4.1 prompts for each platform's unique characteristics
"""

from typing import Dict, Any

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
    profile_summary = f"""
Profile: @{profile_data.get('username', 'unknown')}
Name: {profile_data.get('display_name', 'N/A')}
Bio: {(profile_data.get('bio') or 'No bio')[:500]}
Followers: {_num(profile_data.get('follower_count'))}
Following: {_num(profile_data.get('following_count'))}
Content Count: {_num(profile_data.get('posts_count'))}
Verified: {profile_data.get('verified', False)}
Platform: {ctx['name']}
CRITICAL: Any metric marked 'unknown (not exposed by provider)' is MISSING data, not zero.
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

Use numerical scores (0-1) where applicable. Reference platform-specific behaviors."""


def build_authenticity_prompt(platform: str, profile_data: Dict[str, Any]) -> str:
    """Build a platform-optimized authenticity analysis prompt"""
    ctx = get_platform_context(platform)
    
    return f"""You are a cybersecurity expert specializing in fake account detection on {ctx['name']}.

PLATFORM-SPECIFIC AUTHENTICITY SIGNALS:
{', '.join(ctx['authenticity_signals'])}

PROFILE METRICS:
Username: @{profile_data.get('username')}
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
