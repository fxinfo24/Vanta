"""
Dossier Models
Stores deep intelligence snapshots and cross-platform identity links.
"""

from datetime import datetime, timedelta
from . import db
import json


from app.utils.helpers import parse_timestamp as _parse_when
from app.utils.helpers import engagement_rate_percent, posting_cadence


# Thresholds for alerts raised on a run-to-run change. Every rule is arithmetic
# over stored snapshots, so an alert can always be recomputed and checked.
DEFAULT_ALERT_THRESHOLDS = {
    "followers_drop_percent": 3.0,
    "followers_drop_critical_percent": 10.0,
    "bot_likelihood_jump": 0.2,
    "bot_likelihood_critical_at": 0.5,
    "engagement_drop_percent": 30.0,
    "min_posts_for_engagement": 5,
    "cadence_drop_percent": 50.0,
    "posts_removed_count": 3,
}


def alert_thresholds():
    """Configured thresholds merged over the defaults (config `alerts` block)."""
    thresholds = dict(DEFAULT_ALERT_THRESHOLDS)
    try:
        from app.utils.config import load_config
        configured = (load_config() or {}).get("alerts") or {}
        for key, value in configured.items():
            if key in thresholds and isinstance(value, (int, float)):
                thresholds[key] = float(value)
    except Exception:
        pass
    return thresholds

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

        # Posting cadence in Python, not in prose: posts per week across the
        # window the samples actually cover. Two runs that phrase cadence
        # differently cannot disagree if the number is computed once here.
        cadence = posting_cadence(published)
        posts_per_week = cadence["posts_per_week"]

        followers = DossierSnapshot._num(profile.get("followers") or profile.get("follower_count"))
        # Older runs predate `engagement_metrics`; derive the same number from
        # the stored samples so their snapshots stay comparable.
        rate = DossierSnapshot._num(evidence.get("rate_percent"))
        if rate is None and measured:
            rate = engagement_rate_percent(followers, reactions + comments + shares, measured)
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
            "posts_per_week": posts_per_week,
            "cadence_span_days": cadence["span_days"],
            "dated_posts": cadence["posts"],
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

    @staticmethod
    def compute_alerts(current: dict, previous: dict, elapsed_hours=None, thresholds=None) -> dict:
        """Threshold alerts for one run-to-run change.

        Deterministic: every alert names the metric, both values and the rule
        that fired, so a customer can reproduce it. Rules whose inputs were not
        collected are reported as not evaluated instead of silently passing.
        """
        cur, prev = current or {}, previous or {}
        th = thresholds or alert_thresholds()
        alerts, skipped = [], []

        def add(rule, severity, message, metric, previous_value, current_value, basis):
            alerts.append({
                "rule": rule,
                "severity": severity,
                "message": message,
                "metric": metric,
                "previous": previous_value,
                "current": current_value,
                "basis": basis,
            })

        # 1. Followers
        f_prev, f_cur = DossierSnapshot._num(prev.get("followers")), DossierSnapshot._num(cur.get("followers"))
        if f_prev and f_cur is not None:
            pct = 100.0 * (f_cur - f_prev) / f_prev
            if pct <= -th["followers_drop_critical_percent"]:
                add("followers_drop", "critical",
                    f"Follower count fell {abs(pct):.1f}% ({int(f_prev)} to {int(f_cur)}).",
                    "followers", f_prev, f_cur,
                    f"drop >= {th['followers_drop_critical_percent']}% threshold")
            elif pct <= -th["followers_drop_percent"]:
                add("followers_drop", "warning",
                    f"Follower count fell {abs(pct):.1f}% ({int(f_prev)} to {int(f_cur)}).",
                    "followers", f_prev, f_cur,
                    f"drop >= {th['followers_drop_percent']}% threshold")
        else:
            skipped.append({"rule": "followers_drop", "reason": "follower count missing in one of the runs"})

        # 2. Bot likelihood / authenticity risk
        b_prev, b_cur = DossierSnapshot._num(prev.get("bot_likelihood")), DossierSnapshot._num(cur.get("bot_likelihood"))
        if b_prev is not None and b_cur is not None:
            jump = b_cur - b_prev
            if jump >= th["bot_likelihood_jump"] or (
                b_cur >= th["bot_likelihood_critical_at"] and b_prev < th["bot_likelihood_critical_at"]
            ):
                severity = "critical" if b_cur >= th["bot_likelihood_critical_at"] else "warning"
                add("bot_likelihood_jump", severity,
                    f"Bot likelihood rose from {b_prev:.2f} to {b_cur:.2f}"
                    + (" and crossed the high-risk line." if severity == "critical" else "."),
                    "bot_likelihood", b_prev, b_cur,
                    f"jump >= {th['bot_likelihood_jump']} or crossing {th['bot_likelihood_critical_at']}")
        else:
            skipped.append({"rule": "bot_likelihood_jump",
                            "reason": "authenticity was not assessed in one of the runs"})

        # 3. Engagement rate — only meaningful when both runs measured enough posts
        e_prev, e_cur = (DossierSnapshot._num(prev.get("engagement_rate_percent")),
                         DossierSnapshot._num(cur.get("engagement_rate_percent")))
        n_prev = DossierSnapshot._num(prev.get("posts_measured")) or 0
        n_cur = DossierSnapshot._num(cur.get("posts_measured")) or 0
        minimum = th["min_posts_for_engagement"]
        if e_prev and e_cur is not None and n_prev >= minimum and n_cur >= minimum:
            pct = 100.0 * (e_cur - e_prev) / e_prev
            if pct <= -th["engagement_drop_percent"]:
                add("engagement_drop", "warning",
                    f"Engagement rate fell {abs(pct):.1f}% ({e_prev}% to {e_cur}%).",
                    "engagement_rate_percent", e_prev, e_cur,
                    f"drop >= {th['engagement_drop_percent']}% over {int(n_cur)} measured posts")
        else:
            skipped.append({
                "rule": "engagement_drop",
                "reason": f"needs engagement on both runs with >= {minimum} measured posts "
                          f"(had {int(n_prev)} then {int(n_cur)})",
            })

        # 4. Posting cadence (posts per week over each run's own window)
        c_prev = DossierSnapshot._num(prev.get("posts_per_week"))
        c_cur = DossierSnapshot._num(cur.get("posts_per_week"))
        if c_prev and c_cur is not None:
            pct = 100.0 * (c_cur - c_prev) / c_prev
            if pct <= -th["cadence_drop_percent"]:
                add("cadence_drop", "warning",
                    f"Posting cadence fell {abs(pct):.1f}% ({c_prev}/week to {c_cur}/week).",
                    "posts_per_week", c_prev, c_cur,
                    f"drop >= {th['cadence_drop_percent']}% threshold")
        else:
            skipped.append({"rule": "cadence_drop",
                            "reason": "fewer than two dated posts in one of the runs"})

        # 5. Removed content — only when both runs saw a comparable post set
        delta = DossierSnapshot.compute_delta(cur, prev)
        content = delta.get("content") or {}
        if content.get("comparable"):
            removed = content.get("removed_count") or 0
            if removed >= th["posts_removed_count"]:
                add("content_removed", "warning",
                    f"{removed} previously collected post(s) are no longer present.",
                    "removed_posts", None, removed,
                    f"removed >= {th['posts_removed_count']} with comparable coverage "
                    f"({content.get('coverage_ratio')} of the earlier set)")
        else:
            skipped.append({"rule": "content_removed",
                            "reason": content.get("coverage_note") or "post sets not comparable"})

        # 6. Identity changes
        profile = delta.get("profile") or {}
        if profile.get("display_name_changed"):
            add("display_name_changed", "info",
                f"Display name changed from {prev.get('display_name')!r} to {cur.get('display_name')!r}.",
                "display_name", prev.get("display_name"), cur.get("display_name"), "exact comparison")
        if profile.get("verified_changed"):
            add("verified_status_changed", "warning",
                f"Verified badge {'lost' if prev.get('verified') else 'gained'}.",
                "verified", bool(prev.get("verified")), bool(cur.get("verified")), "exact comparison")
        if profile.get("bio_changed"):
            add("bio_changed", "info", "Profile bio text changed.",
                "bio", None, None, "exact comparison")

        return {
            "alerts": alerts,
            "not_evaluated": skipped,
            "thresholds": {k: th[k] for k in sorted(th)},
            "elapsed_hours": elapsed_hours,
        }

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
            "posts_per_week": move("posts_per_week"),
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

# Cache scope for runs with no signed-in user: a CLI or desktop run belongs to
# the operator of that machine, and every web/Celery user has a positive id.
LOCAL_CACHE_OWNER = 0


class DossierCache(db.Model):
    """Last collected raw dossier for one (user, platform, profile).

    A deep run costs ~14 provider credits, and re-running the analysis on data
    that has not changed wastes all of them. The payload stored here is exactly
    the raw dossier a run would have collected, so re-analysis reads it instead
    of scraping again; only an expired entry triggers a new collection.

    Scoped per user: two users watching the same handle each pay for their own
    collection rather than reading each other's captured data.
    """
    __tablename__ = 'dossier_cache'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True, nullable=False)
    platform = db.Column(db.String(50), nullable=False)
    profile_id = db.Column(db.String(255), nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    collected_at = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'platform', 'profile_id', name='uq_dossier_cache_key'),
    )

    def to_dict(self):
        return {
            'platform': self.platform,
            'profile_id': self.profile_id,
            'collected_at': self.collected_at.isoformat() if self.collected_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'has_payload': bool(self.payload),
        }


class ProviderCreditUsage(db.Model):
    """Last balance a data provider reported, persisted so it survives deploys.

    The balance used to live in a JSON file next to the code, which meant a
    hosted instance always reported "unknown" and the pre-flight guard could
    never fire - the exact failure that let a run collect zero posts.
    """
    __tablename__ = 'provider_credit_usage'

    provider = db.Column(db.String(50), primary_key=True)
    credits_remaining = db.Column(db.Integer, nullable=True)
    # Fingerprint of the API key that produced this balance: the number belongs
    # to one provider account, so a key change makes it meaningless.
    key_fingerprint = db.Column(db.String(32), nullable=True)
    observed_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'credits_remaining': self.credits_remaining,
            'key_fingerprint': self.key_fingerprint,
            'observed_at': self.observed_at.isoformat() if self.observed_at else None,
        }


def record_provider_credits(provider: str, remaining, key_fingerprint=None) -> bool:
    """Upsert an observed balance. Returns False when it could not be stored."""
    if remaining is None:
        return False
    try:
        value = int(remaining)
    except (TypeError, ValueError):
        return False
    try:
        row = db.session.get(ProviderCreditUsage, provider)
        if row is None:
            row = ProviderCreditUsage(provider=provider)
            db.session.add(row)
        row.credits_remaining = value
        if key_fingerprint:
            row.key_fingerprint = key_fingerprint
        row.observed_at = datetime.utcnow()
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False


def read_provider_credits(provider: str):
    """Stored balance row as a dict, or None."""
    try:
        row = db.session.get(ProviderCreditUsage, provider)
    except Exception:
        return None
    return row.to_dict() if row is not None else None


def get_cached_dossier(session, user_id, platform: str, profile_id: str,
                       now: datetime = None):
    """Return a fresh cached dossier payload, or None when absent/expired."""
    now = now or datetime.utcnow()
    row = session.query(DossierCache).filter_by(
        user_id=user_id, platform=platform, profile_id=profile_id
    ).first()
    if row is None or row.expires_at is None or row.expires_at <= now:
        return None
    payload = row.payload
    # Entries collected before the normalizer stopped defaulting a missing
    # badge to False still say "not verified" about accounts whose provider
    # never sent the field. The raw provider payload is stored alongside, so the
    # value is re-derived from it instead of charging the user a re-collection.
    profile = payload.get("profile") if isinstance(payload, dict) else None
    raw = profile.get("raw") if isinstance(profile, dict) else None
    if isinstance(raw, dict):
        verified = raw.get("verified")
        profile["verified"] = verified if verified is not None else raw.get("is_verified")
    return payload


def store_cached_dossier(session, user_id, platform: str, profile_id: str,
                         payload: dict, collected_at: datetime = None,
                         ttl_hours: int = 12):
    """Insert or refresh the cache entry for this subject."""
    if not isinstance(payload, dict) or not payload:
        return None
    now = datetime.utcnow()
    row = session.query(DossierCache).filter_by(
        user_id=user_id, platform=platform, profile_id=profile_id
    ).first()
    if row is None:
        row = DossierCache(user_id=user_id, platform=platform, profile_id=profile_id)
        session.add(row)
    row.payload = payload
    row.collected_at = collected_at or now
    row.expires_at = now + timedelta(hours=max(int(ttl_hours), 1))
    session.commit()
    return row


def purge_expired_cache(session, now: datetime = None) -> int:
    """Drop cache entries past their TTL (they hold raw post text)."""
    now = now or datetime.utcnow()
    removed = session.query(DossierCache).filter(DossierCache.expires_at <= now).delete(
        synchronize_session=False
    )
    if removed:
        session.commit()
    return removed


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


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------
# Raw posts are the most sensitive thing this app stores (they are somebody
# else's words) and the least useful over time; the snapshot rows hold numbers,
# so trend history survives their deletion. These helpers are pure functions of
# a session so both the Celery beat job and tests can call them.

def purge_expired_results(session, now: datetime = None, raw_days: int = 30,
                          quote_days: int = 90) -> dict:
    """Delete collected posts and verbatim quotes past their retention windows.

    ``raw_days``  - age after which the raw dossier (posts, bio, transcripts) goes
    ``quote_days`` - age after which quoted evidence inside analyses goes

    Snapshot rows are never touched: they are aggregate numbers, which is what
    keeps "followers changed by +40 since March" answerable after the posts are
    gone. Returns counts of tasks changed, not rows deleted.
    """
    import copy
    from . import Task, TaskStatus

    now = now or datetime.utcnow()
    raw_cutoff = now - timedelta(days=raw_days)
    quote_cutoff = now - timedelta(days=quote_days)

    raw_purged = quotes_purged = 0
    tasks = Task.query.filter(Task.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED])).all()

    for task in tasks:
        result = task.result_data
        if not isinstance(result, dict) or not result:
            continue
        stamped = task.completed_at or task.updated_at or task.created_at
        if stamped is None:
            continue

        new = None
        if stamped <= raw_cutoff and (result.get("raw_dossier") or result.get("raw_data")):
            new = copy.deepcopy(result)
            new.pop("raw_dossier", None)
            new.pop("raw_data", None)
            profile = new.get("profile_info")
            if isinstance(profile, dict):
                # The bio is quoted text, not a metric.
                for key in ("bio", "description"):
                    profile.pop(key, None)
            new["retention"] = {**(new.get("retention") or {}),
                                "raw_content_removed_at": now.isoformat()}
            raw_purged += 1

        if stamped <= quote_cutoff:
            target = new if new is not None else copy.deepcopy(result)
            removed = _strip_quotes(target)
            if removed:
                target["retention"] = {**(target.get("retention") or {}),
                                       "quotes_removed_at": now.isoformat(),
                                       "quotes_removed": removed}
                new = target
                quotes_purged += 1

        if new is not None:
            task.result_data = new
            session.add(task)

    if raw_purged or quotes_purged:
        session.commit()
    return {"raw_purged": raw_purged, "quotes_purged": quotes_purged}


def _strip_quotes(payload: dict) -> int:
    """Remove verbatim quote lists from an analysis, keeping the counts."""
    removed = 0

    def strip_evidence(container, key="evidence"):
        nonlocal removed
        if not isinstance(container, dict):
            return
        evidence = container.get(key)
        if isinstance(evidence, list) and evidence:
            removed += len(evidence)
            container[key] = []
            container["evidence_removed_by_retention"] = True
        elif isinstance(evidence, dict):
            total = sum(len(v) for v in evidence.values() if isinstance(v, list))
            if total:
                removed += total
                container[key] = {}
                container["evidence_removed_by_retention"] = True

    for section in ("content_analysis", "consumer_profile", "behavioral_profile",
                    "authenticity", "belief_system"):
        strip_evidence(payload.get(section))
    strip_evidence(payload)

    calibration = ((payload.get("belief_system") or {}).get("EVIDENCE_AND_CALIBRATION")
                   or (payload.get("belief_system") or {}).get("EVIDENCE AND CALIBRATION"))
    if isinstance(calibration, dict):
        strip_evidence(calibration)

    return removed
