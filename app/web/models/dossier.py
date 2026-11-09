"""
Dossier Models
Stores deep intelligence snapshots and cross-platform identity links.
"""

from datetime import datetime
from . import db
import json

class DossierSnapshot(db.Model):
    """
    Stores point-in-time snapshots of collected data.
    Designed to track changes in a target's digital footprint over time.
    """
    __tablename__ = 'dossier_snapshot'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), index=True)
    platform = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(255), nullable=False)
    
    # Core Data
    snapshot_data = db.Column(db.JSON)     # The full raw collection data
    analysis_data = db.Column(db.JSON)     # The AI analysis results
    
    # Metadata
    collection_mode = db.Column(db.String(20)) # 'quick' or 'deep'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # For quick retrieval
    summary_text = db.Column(db.Text)      # Executive summary
    risk_score = db.Column(db.Float)       # Authenticity/Risk score (0-1)
    
    # Vector Embedding Placeholder (for future pgvector migration)
    # Stores semantic embedding of the profile for similarity search
    # embedding = db.Column(Vector(1536)) 
    embedding_json = db.Column(db.JSON)    # Temporary storage for embeddings

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "platform": self.platform,
            "username": self.username,
            "collection_mode": self.collection_mode,
            "created_at": self.created_at.isoformat(),
            "risk_score": self.risk_score,
            "summary": self.summary_text
        }

    # ------------------------------------------------------------------
    # Snapshot construction + comparison
    # ------------------------------------------------------------------
    # A single analysis is a photograph. Value comes from comparing two of
    # them: what moved, what appeared, what disappeared. Metrics are computed
    # here (deterministically) rather than asked of a model, so a delta is
    # reproducible from the stored snapshots alone.

    @staticmethod
    def _num(value):
        return value if isinstance(value, (int, float)) else None

    @staticmethod
    def metrics_from_result(result: dict) -> dict:
        """Extract comparable, pre-computed metrics from an analysis result."""
        result = result or {}
        profile = result.get("profile_info") or {}
        stats = result.get("raw_stats") or {}
        auth = result.get("authenticity") or {}
        belief = result.get("belief_system") or {}
        compass = belief.get("POLITICAL_COMPASS") or belief.get("POLITICAL COMPASS") or {}
        evidence = (auth.get("engagement_metrics") or {})

        dossier = result.get("raw_dossier") or {}
        items = dossier.get("content") or []
        post_ids = []
        media = {"video": 0, "image": 0}
        measured = reactions = comments = shares = 0
        published = []
        for item in items:
            if not isinstance(item, dict):
                continue
            when = item.get("creation_time") or item.get("created_at") or item.get("publishTime")
            if isinstance(when, str) and when.strip():
                published.append(when.strip())
            elif isinstance(when, (int, float)):  # epoch seconds
                published.append(datetime.utcfromtimestamp(when).isoformat() + "Z")
            pid = item.get("id") or item.get("post_id")
            if pid:
                post_ids.append(str(pid))
            url = item.get("url") or item.get("permalink") or ""
            if item.get("videoDetails") or "/reel/" in url or "/watch" in url or "/videos/" in url:
                media["video"] += 1
            elif item.get("image") or item.get("images"):
                media["image"] += 1
            if any(item.get(k) is not None for k in
                   ("reactionCount", "share_count", "commentCount", "reaction_count")):
                measured += 1
                reactions += int(item.get("reactionCount", item.get("reaction_count")) or 0)
                comments += int(item.get("commentCount", item.get("comment_count")) or 0)
                shares += int(item.get("share_count", item.get("shares")) or 0)

        followers = DossierSnapshot._num(profile.get("followers") or profile.get("follower_count"))
        # Older runs predate `engagement_metrics`; derive the same number from
        # the stored samples so their snapshots stay comparable.
        rate = DossierSnapshot._num(evidence.get("rate_percent"))
        if rate is None and measured and followers:
            rate = round(100.0 * ((reactions + comments + shares) / measured) / float(followers), 3)
            evidence = {"rate_percent": rate, "posts_measured": measured,
                        "reactions": reactions, "comments": comments, "shares": shares}

        return {
            "followers": followers,
            "following": DossierSnapshot._num(profile.get("following") or profile.get("following_count")),
            "posts_count": DossierSnapshot._num(profile.get("posts") or profile.get("posts_count")),
            "verified": profile.get("verified"),
            "display_name": profile.get("display_name"),
            "bio": (profile.get("bio") or "")[:280],
            "profile_image_present": bool(profile.get("profile_image_url")),
            "engagement_rate_percent": DossierSnapshot._num(evidence.get("rate_percent")),
            "posts_measured": evidence.get("posts_measured") or measured or stats.get("content_items_collected"),
            "reactions": evidence.get("reactions"),
            "comments": evidence.get("comments"),
            "shares": evidence.get("shares"),
            "comments_collected": stats.get("comments_collected"),
            "video_items": media["video"],
            "image_items": media["image"],
            "post_ids": post_ids,
            "post_window": {
                "earliest": min(published) if published else None,
                "latest": max(published) if published else None,
            },
            "risk_assessment": auth.get("risk_assessment"),
            "bot_likelihood": DossierSnapshot._num(auth.get("bot_likelihood")),
            "trust_score": DossierSnapshot._num((auth.get("overall_authenticity") or {}).get("score")),
            "political_label": compass.get("label"),
            "economic_axis": DossierSnapshot._num(compass.get("economic_axis")),
            "social_axis": DossierSnapshot._num(compass.get("social_axis")),
            "topical_focus": ((auth.get("topical_focus") or {}).get("primary_topic")),
        }

    @staticmethod
    def _has_data(metrics: dict) -> bool:
        """A run that fetched nothing must not become a trend data point."""
        return bool(
            metrics.get("followers")
            or metrics.get("posts_measured")
            or metrics.get("bio")
            or metrics.get("post_ids")
        )

    @classmethod
    def build(cls, task_id, platform, username, result, collection_mode=None):
        """Return a snapshot row ready to add, or None when nothing was collected."""
        metrics = cls.metrics_from_result(result)
        if not cls._has_data(metrics):
            return None
        return cls(
            task_id=task_id,
            platform=(platform or "unknown").lower(),
            username=str(username or "unknown"),
            snapshot_data=metrics,
            analysis_data={
                "risk_assessment": metrics.get("risk_assessment"),
                "bot_likelihood": metrics.get("bot_likelihood"),
                "trust_score": metrics.get("trust_score"),
                "political_label": metrics.get("political_label"),
                "topical_focus": metrics.get("topical_focus"),
            },
            collection_mode=collection_mode,
            summary_text=(result or {}).get("executive_summary"),
            risk_score=metrics.get("trust_score"),
        )

    @staticmethod
    def compute_delta(current: dict, previous: dict) -> dict:
        """Compare two ``snapshot_data`` payloads. Every field is optional."""
        cur = current or {}
        prev = previous or {}

        def move(key):
            a, b = DossierSnapshot._num(prev.get(key)), DossierSnapshot._num(cur.get(key))
            if a is None or b is None:
                return {"previous": a, "current": b, "change": None, "change_percent": None}
            change = round(b - a, 4)
            pct = round(100.0 * change / a, 2) if a else None
            return {"previous": a, "current": b, "change": change, "change_percent": pct}

        prev_ids, cur_ids = set(prev.get("post_ids") or []), set(cur.get("post_ids") or [])
        new_posts = sorted(cur_ids - prev_ids)
        gone_posts = sorted(prev_ids - cur_ids)

        # A run that collected 12 posts cannot report 28 deletions against a run
        # that collected 40: that is a smaller sample, not vanished content.
        # Absence only counts as deletion when coverage is comparable.
        prev_n, cur_n = len(prev_ids), len(cur_ids)
        coverage_ratio = round(cur_n / prev_n, 2) if prev_n else None
        comparable = bool(prev_n and cur_n and coverage_ratio >= 0.7)
        if not comparable:
            coverage_note = (
                "Post sets are not comparable: the runs collected different numbers of "
                f"items ({prev_n} then {cur_n}). Absence here is sampling, not deletion."
            )
            new_posts, gone_posts = [], []
            new_count = removed_count = None
        else:
            coverage_note = None
            new_count, removed_count = len(new_posts), len(gone_posts)

        return {
            "followers": move("followers"),
            "engagement_rate_percent": move("engagement_rate_percent"),
            "posts_measured": move("posts_measured"),
            "bot_likelihood": move("bot_likelihood"),
            "trust_score": move("trust_score"),
            "risk": {
                "previous": prev.get("risk_assessment"),
                "current": cur.get("risk_assessment"),
                "changed": prev.get("risk_assessment") != cur.get("risk_assessment"),
            },
            "political_label": {
                "previous": prev.get("political_label"),
                "current": cur.get("political_label"),
                "changed": prev.get("political_label") != cur.get("political_label"),
            },
            "topical_focus": {
                "previous": prev.get("topical_focus"),
                "current": cur.get("topical_focus"),
                "changed": prev.get("topical_focus") != cur.get("topical_focus"),
            },
            "profile": {
                "bio_changed": (prev.get("bio") or "") != (cur.get("bio") or ""),
                "display_name_changed": prev.get("display_name") != cur.get("display_name"),
                "verified_changed": bool(prev.get("verified")) != bool(cur.get("verified")),
            },
            "content": {
                "comparable": comparable,
                "coverage_ratio": coverage_ratio,
                "coverage_note": coverage_note,
                "new_post_ids": new_posts[:25],
                "removed_post_ids": gone_posts[:25],
                "new_count": new_count,
                "removed_count": removed_count,
                "retained_count": len(prev_ids & cur_ids),
                "window": {
                    "previous": prev.get("post_window") or {},
                    "current": cur.get("post_window") or {},
                },
            },
        }

class CrossPlatformProfile(db.Model):
    """
    Links multiple platform profiles to a single human identity.
    "The Digital Soul"
    """
    __tablename__ = 'cross_platform_profile'

    id = db.Column(db.Integer, primary_key=True)
    identity_name = db.Column(db.String(255))  # e.g., "John Doe"
    
    # Linked Accounts Map: { 'twitter': 'jdoe', 'instagram': 'johnnyd' }
    platforms = db.Column(db.JSON, default=dict)
    
    # Discovered but unverified links
    potential_links = db.Column(db.JSON, default=list)
    
    # Aggregated Stats
    total_followers = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "identity_name": self.identity_name,
            "platforms": self.platforms,
            "total_followers": self.total_followers,
            "last_updated": self.last_updated.isoformat()
        }
