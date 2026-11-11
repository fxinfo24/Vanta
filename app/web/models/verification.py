# Vanta Verification Models - SQLAlchemy models for 7-layer verification
# CONSOLIDATED: superset schema so Product A (Task/TaskStatus, 21 platforms)
# and Product B (ingestion/claim/fact/temporal/rag/evidence) share one DB.
# Existing columns preserved; new columns are nullable for backwards compat.
from datetime import datetime
from enum import Enum
from . import db
from typing import Any, Optional
from sqlalchemy.ext.hybrid import hybrid_property


class ClaimStatus(Enum):
    EXTRACTED = "extracted"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ClaimType(Enum):
    FACTUAL = "factual"
    OPINION = "opinion"
    SATIRE = "satire"
    OTHER = "other"


class LanguageCode(Enum):
    EN = "en"
    BN = "bn"
    UNKNOWN = "unknown"


class Platform(Enum):
    # Product B original
    FACEBOOK = "facebook"
    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    # Product A (21-platform) additions — must live in same Enum table
    YOUTUBE = "youtube"
    LINKEDIN = "linkedin"
    REDDIT = "reddit"
    PINTEREST = "pinterest"
    SNAPCHAT = "snapchat"
    THREADS = "threads"
    BLUESKY = "bluesky"
    TWITCH = "twitch"
    KICK = "kick"
    GITHUB = "github"
    LINKTREE = "linktree"
    KOMI = "komi"
    PILLAR = "pillar"
    LINKBIO = "linkbio"
    GOOGLE = "google"
    TIKTOK_SHOP = "tiktok_shop"
    AMAZON_SHOP = "amazon_shop"


class MediaType(Enum):
    PHOTO = "Photo"
    VIDEO = "Video"
    GENERIC = "GenericAttachmentMedia"
    # Ingestor additions
    TEXT = "text"
    OTHER = "other"


class SocialMediaType(Enum):
    FACEBOOK = "facebook"
    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"


class SourceType(Enum):
    OFFICIAL = "official"
    NEWS = "news"
    FACT_CHECK = "fact_check"
    SOCIAL = "social"
    ACADEMIC = "academic"
    ARCHIVE = "archive"


class VerificationStatus(Enum):
    # Existing Product B values (kept)
    TRUE = "true"
    FALSE = "false"
    LIKELY_TRUE = "likely_true"
    MISLEADING = "misleading"
    DISPUTED = "disputed"
    UNVERIFIED = "unverified"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ERROR = "error"
    # Fact-check + RAG pipeline values (required by engine/rag_engine)
    VERIFIED_TRUE = "verified_true"
    VERIFIED_FALSE = "verified_false"
    # RAG/LLM analyzer verdict values
    UNVERIFIABLE = "unverifiable"
    NO_MATCH = "no_match"


# Map legacy values onto new values and vice-versa for backwards compat
_STATUS_ALIASES = {
    VerificationStatus.TRUE: VerificationStatus.VERIFIED_TRUE,
    VerificationStatus.FALSE: VerificationStatus.VERIFIED_FALSE,
    VerificationStatus.UNVERIFIED: VerificationStatus.UNVERIFIABLE,
}


def _coerce_status(value):
    """Coerce string/enum/status aliases to canonical VerificationStatus."""
    if value is None:
        return None
    if isinstance(value, VerificationStatus):
        # Normalize already-mapped values? Keep as-is to avoid cycles.
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        # Direct enum value / name match
        for member in VerificationStatus:
            if member.value == s or member.name.lower() == s:
                return member
        # Legacy aliases
        _str_alias = {
            "true": VerificationStatus.VERIFIED_TRUE,
            "verified_true": VerificationStatus.VERIFIED_TRUE,
            "verified": VerificationStatus.VERIFIED_TRUE,
            "false": VerificationStatus.VERIFIED_FALSE,
            "verified_false": VerificationStatus.VERIFIED_FALSE,
            "unverified": VerificationStatus.UNVERIFIABLE,
            "unverifiable": VerificationStatus.UNVERIFIABLE,
            "no_match": VerificationStatus.UNVERIFIABLE,
            "likely_true": VerificationStatus.LIKELY_TRUE,
            "misleading": VerificationStatus.MISLEADING,
            "disputed": VerificationStatus.DISPUTED,
            "insufficient_evidence": VerificationStatus.INSUFFICIENT_EVIDENCE,
            "error": VerificationStatus.ERROR,
        }
        return _str_alias.get(s)
    return value


class SocialMediaPost(db.Model):
    """Original post with extracted claims

    Consolidated schema:
    - Keeps the old columns (platform String, profile_id, content, raw_data,
      detected_language, processed_for_claims, processed_at, created_at).
    - Adds every field the Apify ingestor constructs, plus the fields the
      claim extractor (post.text) and temporal verifier (post.timestamp)
      read, via hybrid properties aliased to content/timestamp columns so
      existing Product-B CLI code does not break.
    """
    __tablename__ = 'social_media_posts'

    # PK: String so Product B ids like "facebook_123" work. Old Integer ids
    # remain readable via migration (existing DBs need table rebuild — see
    # directives/api.md + migration note). New DBs are created as String.
    id = db.Column(db.String(255), primary_key=True)
    # Owner of this post (authenticated user). Nullable for legacy/CLI rows;
    # API-created posts are always stamped and queries scoped to it.
    user_id = db.Column(db.Integer, nullable=True, index=True)
    # Kept as String for Product A compatibility; Product B passes
    # Platform enum values, which Flask-SQLAlchemy/String columns accept
    # via str conversion; we normalize in constructors via coerce helper.
    platform = db.Column(db.String(50), nullable=False)
    profile_id = db.Column(db.String(255))
    content = db.Column(db.Text)
    raw_data = db.Column(db.JSON)
    detected_language = db.Column(db.Enum(LanguageCode), default=LanguageCode.UNKNOWN)
    processed_for_claims = db.Column(db.Boolean, default=False)
    processed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- Ingestion superset (nullable, Product B writes all of these) ---
    platform_post_id = db.Column(db.String(255))
    author_id = db.Column(db.String(255))
    author_name = db.Column(db.String(255))
    author_profile_url = db.Column(db.String(500))
    text = db.Column(db.Text)
    text_hash = db.Column(db.String(64))
    detected_language_confidence = db.Column(db.Float, default=0.0)
    created_at_platform = db.Column(db.DateTime)
    likes_count = db.Column(db.Integer, default=0)
    comments_count = db.Column(db.Integer, default=0)
    shares_count = db.Column(db.Integer, default=0)
    views_count = db.Column(db.Integer, default=0)
    reaction_like_count = db.Column(db.Integer, default=0)
    reaction_love_count = db.Column(db.Integer, default=0)
    reaction_haha_count = db.Column(db.Integer, default=0)
    reaction_wow_count = db.Column(db.Integer, default=0)
    reaction_sad_count = db.Column(db.Integer, default=0)
    reaction_angry_count = db.Column(db.Integer, default=0)
    reaction_care_count = db.Column(db.Integer, default=0)
    # The `mediatype` enum in the database is labelled with the member *values*
    # (Photo, Video, GenericAttachmentMedia, text, other). Without
    # values_callable SQLAlchemy reads and writes member *names*, so loading any
    # ingested post raised LookupError: 'text' is not among the defined enum
    # values - every row was unreadable, which is what broke the posts list.
    media_type = db.Column(
        db.Enum(MediaType, values_callable=lambda enum: [m.value for m in enum]),
        nullable=True,
    )
    media_urls = db.Column(db.JSON)
    media_metadata = db.Column(db.JSON)
    post_url = db.Column(db.String(500))
    platform_profile_url = db.Column(db.String(500))
    quality_score = db.Column(db.Float, default=0.0)
    completeness_score = db.Column(db.Float, default=0.0)
    timestamp_validity_score = db.Column(db.Float, default=0.0)

    # `timestamp` is read by TemporalVerifier.extract_claim_date; the
    # ingestor stores platform time in created_at_platform and DB time
    # in created_at. Expose a hybrid property that prefers platform time.
    @property
    def timestamp(self):
        return self.created_at_platform or self.created_at

    @timestamp.setter
    def timestamp(self, value):
        if isinstance(value, datetime):
            self.created_at_platform = value
        elif value is not None:
            self.created_at_platform = value
            if self.created_at is None:
                self.created_at = value

    # text/content sync: ingestor + extractor use .text; old rows use .content
    @property
    def text_content(self):
        return self.text or self.content

    claims = db.relationship('Claim', backref='post', lazy=True)


class Claim(db.Model):
    """Extracted claim from post"""
    __tablename__ = 'claims'

    id = db.Column(db.String(255), primary_key=True)
    post_id = db.Column(db.String(255), db.ForeignKey('social_media_posts.id'))
    claim_text = db.Column(db.Text, nullable=False)
    claim_hash = db.Column(db.String(64))
    claim_type = db.Column(db.Enum(ClaimType), default=ClaimType.OTHER)
    claim_type_confidence = db.Column(db.Float, default=0.0)
    check_worthiness_score = db.Column(db.Float, default=0.0)
    sentence_index = db.Column(db.Integer, default=0)
    entities = db.Column(db.JSON)
    detected_language = db.Column(db.Enum(LanguageCode), default=LanguageCode.UNKNOWN)
    detected_language_confidence = db.Column(db.Float, default=0.5)
    extraction_model = db.Column(db.String(100))
    extracted_at = db.Column(db.DateTime, default=datetime.utcnow)

    verifications = db.relationship('VerificationResult', backref='claim', lazy=True)


class VerificationResult(db.Model):
    """Result of verification across all layers

    Consolidated: keeps status/confidence/evidence_chain/reasoning/created_at
    and adds the columns written by fact-check (Layer 4), temporal (Layer 5),
    RAG (Layer 6) and ConfidenceScorer (Layer 7) engines.
    """
    __tablename__ = 'verification_results'

    id = db.Column(db.String(255), primary_key=True)
    claim_id = db.Column(db.String(255), db.ForeignKey('claims.id'))
    status = db.Column(db.String(50))
    confidence_score = db.Column(db.Float)
    evidence_chain = db.Column(db.JSON)
    reasoning = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- Pipeline superset ---
    verification_status = db.Column(db.Enum(VerificationStatus), nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    fact_check_matches = db.Column(db.JSON, nullable=True)
    fact_check_verdict = db.Column(db.String(100), nullable=True)
    fact_check_sources = db.Column(db.JSON, nullable=True)
    fact_check_similarity_score = db.Column(db.Float, nullable=True)
    composite_verification_score = db.Column(db.Float, nullable=True)

    @property
    def status_value(self):
        """String representation for JSON responses / legacy readers."""
        if self.verification_status is not None:
            v = self.verification_status
            return v.value if isinstance(v, VerificationStatus) else str(v)
        return self.status


def _bind_status_hybrid():
    """Expose .status and .verification_status as synced hybrids.

    The legacy `status` column stays for backwards compat; new code uses
    `verification_status`. Reading `.status` returns the canonical string
    value of verification_status when present so old readers that expect
    `status.value` keep working when verification_status is set.
    """
    pass


class FactCheckSource(db.Model):
    """Fact-check source (for ingestion CLI)"""
    __tablename__ = 'fact_check_sources'

    id = db.Column(db.String(255), primary_key=True)
    name = db.Column(db.String(255))
    url = db.Column(db.String(500))
    # Superset columns written by the fact-check CLI registry
    api_endpoint = db.Column(db.String(500), nullable=True)
    api_key_required = db.Column(db.Boolean, default=False)
    languages_supported = db.Column(db.JSON, nullable=True)
    regions_covered = db.Column(db.JSON, nullable=True)
    reliability_score = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True)


class ExternalFactCheck(db.Model):
    """External fact-check result"""
    __tablename__ = 'external_fact_checks'

    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.String(255), db.ForeignKey('claims.id'))
    source_id = db.Column(db.String(255), db.ForeignKey('fact_check_sources.id'))
    claim_text = db.Column(db.Text)
    rating = db.Column(db.String(50))
    url = db.Column(db.String(500))
    excerpt = db.Column(db.Text)


def create_tables():
    """Create verification tables"""
    db.create_all()


# --- Sync helpers (keep both schemas authoritative) ---
from sqlalchemy import event as _sa_event


@_sa_event.listens_for(SocialMediaPost, 'init', propagate=True)
def _sync_post_init(target, args, kwargs):
    # platform may arrive as Platform enum (Product B) -> store value string
    plat = kwargs.get('platform')
    if plat is not None and hasattr(plat, 'value'):
        kwargs['platform'] = plat.value
    # text <-> content: keep both columns populated so either reader works
    if kwargs.get('text') and not kwargs.get('content'):
        kwargs['content'] = kwargs['text']
    elif kwargs.get('content') and not kwargs.get('text'):
        kwargs['text'] = kwargs['content']


# NOTE: 'set' is an AttributeEvent — listen on each attribute, not the class
# (listens_for(Model, 'set') raises AttributeError on SQLAlchemy 2.x).
def _sync_post_set(target, value, oldvalue, initiator):
    # Write via __dict__ to avoid re-firing the reciprocal listener (recursion).
    if initiator.key == 'text' and value and not target.__dict__.get('content'):
        target.__dict__['content'] = value
    elif initiator.key == 'content' and value and not target.__dict__.get('text'):
        target.__dict__['text'] = value
    elif initiator.key == 'platform' and hasattr(value, 'value'):
        target.__dict__['platform'] = value.value


_sa_event.listen(SocialMediaPost.text, 'set', _sync_post_set)
_sa_event.listen(SocialMediaPost.content, 'set', _sync_post_set)
_sa_event.listen(SocialMediaPost.platform, 'set', _sync_post_set)


@_sa_event.listens_for(VerificationResult, 'init', propagate=True)
def _sync_vr_init(target, args, kwargs):
    # status may arrive as enum (evidence verifier) -> coerce
    if 'status' in kwargs and kwargs['status'] is not None:
        s = _coerce_status(kwargs['status'])
        if isinstance(s, VerificationStatus):
            kwargs['verification_status'] = s
            if not kwargs.get('status') or not isinstance(kwargs['status'], str):
                kwargs['status'] = s.value
    elif 'verification_status' in kwargs and kwargs['verification_status'] is not None:
        s = _coerce_status(kwargs['verification_status'])
        kwargs['verification_status'] = s
        if s is not None:
            kwargs['status'] = s.value if isinstance(s, VerificationStatus) else str(s)


def _sync_vr_set(target, value, oldvalue, initiator):
    if initiator.key == 'verification_status' and value is not None:
        s = _coerce_status(value)
        if isinstance(s, VerificationStatus):
            target.__dict__['verification_status'] = s
            target.__dict__['status'] = s.value
    elif initiator.key == 'status' and value is not None:
        s = _coerce_status(value)
        if isinstance(s, VerificationStatus):
            target.__dict__['verification_status'] = s
            target.__dict__['status'] = s.value


_sa_event.listen(VerificationResult.verification_status, 'set', _sync_vr_set)
_sa_event.listen(VerificationResult.status, 'set', _sync_vr_set)
