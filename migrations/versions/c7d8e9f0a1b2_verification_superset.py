"""Verification superset schema (Product B consolidation)

Revision ID: c7d8e9f0a1b2
Revises: 6a95d7308ea3
Create Date: 2026-11-08

Creates the consolidated verification tables matching
app/web/models/verification.py in their superset form so Product A
(Task) and Product B (7-layer verification) share one DB.
All new columns are nullable for backwards compatibility.
If tables already exist (created via db.create_all in dev), this
migration is a no-op for create_table guards below.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


revision = 'c7d8e9f0a1b2'
down_revision = '6a95d7308ea3'
branch_labels = None
depends_on = None


def _json_type():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def _table_exists(name):
    return inspect(op.get_bind()).has_table(name)


def upgrade():
    upgrade_add_columns()
    json_type = _json_type()

    if not _table_exists('social_media_posts'):
        op.create_table(
            'social_media_posts',
            sa.Column('id', sa.String(255), nullable=False),
            sa.Column('platform', sa.String(50), nullable=False),
            sa.Column('profile_id', sa.String(255), nullable=True),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('raw_data', json_type, nullable=True),
            sa.Column('detected_language', sa.Enum('EN', 'BN', 'UNKNOWN', name='languagecode'), nullable=True),
            sa.Column('processed_for_claims', sa.Boolean(), nullable=True),
            sa.Column('processed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            # ingestion superset
            sa.Column('platform_post_id', sa.String(255), nullable=True),
            sa.Column('author_id', sa.String(255), nullable=True),
            sa.Column('author_name', sa.String(255), nullable=True),
            sa.Column('author_profile_url', sa.String(500), nullable=True),
            sa.Column('text', sa.Text(), nullable=True),
            sa.Column('text_hash', sa.String(64), nullable=True),
            sa.Column('detected_language_confidence', sa.Float(), nullable=True),
            sa.Column('created_at_platform', sa.DateTime(), nullable=True),
            sa.Column('likes_count', sa.Integer(), nullable=True),
            sa.Column('comments_count', sa.Integer(), nullable=True),
            sa.Column('shares_count', sa.Integer(), nullable=True),
            sa.Column('views_count', sa.Integer(), nullable=True),
            sa.Column('reaction_like_count', sa.Integer(), nullable=True),
            sa.Column('reaction_love_count', sa.Integer(), nullable=True),
            sa.Column('reaction_haha_count', sa.Integer(), nullable=True),
            sa.Column('reaction_wow_count', sa.Integer(), nullable=True),
            sa.Column('reaction_sad_count', sa.Integer(), nullable=True),
            sa.Column('reaction_angry_count', sa.Integer(), nullable=True),
            sa.Column('reaction_care_count', sa.Integer(), nullable=True),
            sa.Column('media_type', sa.Enum('Photo', 'Video', 'GenericAttachmentMedia', 'text', 'other', name='mediatype'), nullable=True),
            sa.Column('media_urls', json_type, nullable=True),
            sa.Column('media_metadata', json_type, nullable=True),
            sa.Column('post_url', sa.String(500), nullable=True),
            sa.Column('platform_profile_url', sa.String(500), nullable=True),
            sa.Column('quality_score', sa.Float(), nullable=True),
            sa.Column('completeness_score', sa.Float(), nullable=True),
            sa.Column('timestamp_validity_score', sa.Float(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('claims'):
        op.create_table(
            'claims',
            sa.Column('id', sa.String(255), nullable=False),
            sa.Column('post_id', sa.String(255), nullable=True),
            sa.Column('claim_text', sa.Text(), nullable=False),
            sa.Column('claim_hash', sa.String(64), nullable=True),
            sa.Column('claim_type', sa.Enum('FACTUAL', 'OPINION', 'SATIRE', 'OTHER', name='claimtype'), nullable=True),
            sa.Column('claim_type_confidence', sa.Float(), nullable=True),
            sa.Column('check_worthiness_score', sa.Float(), nullable=True),
            sa.Column('sentence_index', sa.Integer(), nullable=True),
            sa.Column('entities', json_type, nullable=True),
            sa.Column('detected_language', sa.Enum('EN', 'BN', 'UNKNOWN', name='languagecode'), nullable=True),
            sa.Column('detected_language_confidence', sa.Float(), nullable=True),
            sa.Column('extraction_model', sa.String(100), nullable=True),
            sa.Column('extracted_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['post_id'], ['social_media_posts.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('verification_results'):
        op.create_table(
            'verification_results',
            sa.Column('id', sa.String(255), nullable=False),
            sa.Column('claim_id', sa.String(255), nullable=True),
            sa.Column('status', sa.String(50), nullable=True),
            sa.Column('confidence_score', sa.Float(), nullable=True),
            sa.Column('evidence_chain', json_type, nullable=True),
            sa.Column('reasoning', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('verification_status', sa.Enum('TRUE', 'FALSE', 'LIKELY_TRUE', 'MISLEADING', 'DISPUTED', 'UNVERIFIED', 'INSUFFICIENT_EVIDENCE', 'ERROR', 'VERIFIED_TRUE', 'VERIFIED_FALSE', 'UNVERIFIABLE', 'NO_MATCH', name='verificationstatus'), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('fact_check_matches', json_type, nullable=True),
            sa.Column('fact_check_verdict', sa.String(100), nullable=True),
            sa.Column('fact_check_sources', json_type, nullable=True),
            sa.Column('fact_check_similarity_score', sa.Float(), nullable=True),
            sa.Column('composite_verification_score', sa.Float(), nullable=True),
            sa.ForeignKeyConstraint(['claim_id'], ['claims.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('fact_check_sources'):
        op.create_table(
            'fact_check_sources',
            sa.Column('id', sa.String(255), nullable=False),
            sa.Column('name', sa.String(255), nullable=True),
            sa.Column('url', sa.String(500), nullable=True),
            sa.Column('api_endpoint', sa.String(500), nullable=True),
            sa.Column('api_key_required', sa.Boolean(), nullable=True),
            sa.Column('languages_supported', json_type, nullable=True),
            sa.Column('regions_covered', json_type, nullable=True),
            sa.Column('reliability_score', sa.Float(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('external_fact_checks'):
        op.create_table(
            'external_fact_checks',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('claim_id', sa.String(255), nullable=True),
            sa.Column('source_id', sa.String(255), nullable=True),
            sa.Column('claim_text', sa.Text(), nullable=True),
            sa.Column('rating', sa.String(50), nullable=True),
            sa.Column('url', sa.String(500), nullable=True),
            sa.Column('excerpt', sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(['claim_id'], ['claims.id']),
            sa.ForeignKeyConstraint(['source_id'], ['fact_check_sources.id']),
            sa.PrimaryKeyConstraint('id'),
        )


def _add_missing_columns(table, columns):
    """Add columns present in the superset model but missing on old DBs."""
    existing = {c['name'] for c in inspect(op.get_bind()).get_columns(table)}
    for name, col in columns:
        if name not in existing:
            op.add_column(table, col)


def upgrade_add_columns():
    json_type = _json_type()
    # task: result_data / has_result (persistence fix)
    if _table_exists('task'):
        _add_missing_columns('task', [
            ('result_data', sa.Column('result_data', json_type, nullable=True)),
            ('has_result', sa.Column('has_result', sa.Boolean(), nullable=True, server_default=sa.text('false'))),
        ])
    if _table_exists('social_media_posts'):
        _add_missing_columns('social_media_posts', [
            ('platform_post_id', sa.Column('platform_post_id', sa.String(255), nullable=True)),
            ('author_id', sa.Column('author_id', sa.String(255), nullable=True)),
            ('author_name', sa.Column('author_name', sa.String(255), nullable=True)),
            ('author_profile_url', sa.Column('author_profile_url', sa.String(500), nullable=True)),
            ('text', sa.Column('text', sa.Text(), nullable=True)),
            ('text_hash', sa.Column('text_hash', sa.String(64), nullable=True)),
            ('detected_language_confidence', sa.Column('detected_language_confidence', sa.Float(), nullable=True)),
            ('created_at_platform', sa.Column('created_at_platform', sa.DateTime(), nullable=True)),
            ('likes_count', sa.Column('likes_count', sa.Integer(), nullable=True)),
            ('comments_count', sa.Column('comments_count', sa.Integer(), nullable=True)),
            ('shares_count', sa.Column('shares_count', sa.Integer(), nullable=True)),
            ('views_count', sa.Column('views_count', sa.Integer(), nullable=True)),
            ('reaction_like_count', sa.Column('reaction_like_count', sa.Integer(), nullable=True)),
            ('reaction_love_count', sa.Column('reaction_love_count', sa.Integer(), nullable=True)),
            ('reaction_haha_count', sa.Column('reaction_haha_count', sa.Integer(), nullable=True)),
            ('reaction_wow_count', sa.Column('reaction_wow_count', sa.Integer(), nullable=True)),
            ('reaction_sad_count', sa.Column('reaction_sad_count', sa.Integer(), nullable=True)),
            ('reaction_angry_count', sa.Column('reaction_angry_count', sa.Integer(), nullable=True)),
            ('reaction_care_count', sa.Column('reaction_care_count', sa.Integer(), nullable=True)),
            ('media_type', sa.Column('media_type', sa.String(50), nullable=True)),
            ('media_urls', sa.Column('media_urls', json_type, nullable=True)),
            ('media_metadata', sa.Column('media_metadata', json_type, nullable=True)),
            ('post_url', sa.Column('post_url', sa.String(500), nullable=True)),
            ('platform_profile_url', sa.Column('platform_profile_url', sa.String(500), nullable=True)),
            ('quality_score', sa.Column('quality_score', sa.Float(), nullable=True)),
            ('completeness_score', sa.Column('completeness_score', sa.Float(), nullable=True)),
            ('timestamp_validity_score', sa.Column('timestamp_validity_score', sa.Float(), nullable=True)),
        ])
    if _table_exists('verification_results'):
        _add_missing_columns('verification_results', [
            ('verification_status', sa.Column('verification_status', sa.String(50), nullable=True)),
            ('completed_at', sa.Column('completed_at', sa.DateTime(), nullable=True)),
            ('fact_check_matches', sa.Column('fact_check_matches', json_type, nullable=True)),
            ('fact_check_verdict', sa.Column('fact_check_verdict', sa.String(100), nullable=True)),
            ('fact_check_sources', sa.Column('fact_check_sources', json_type, nullable=True)),
            ('fact_check_similarity_score', sa.Column('fact_check_similarity_score', sa.Float(), nullable=True)),
            ('composite_verification_score', sa.Column('composite_verification_score', sa.Float(), nullable=True)),
        ])
    if _table_exists('fact_check_sources'):
        _add_missing_columns('fact_check_sources', [
            ('api_endpoint', sa.Column('api_endpoint', sa.String(500), nullable=True)),
            ('api_key_required', sa.Column('api_key_required', sa.Boolean(), nullable=True)),
            ('languages_supported', sa.Column('languages_supported', json_type, nullable=True)),
            ('regions_covered', sa.Column('regions_covered', json_type, nullable=True)),
            ('reliability_score', sa.Column('reliability_score', sa.Float(), nullable=True)),
            ('is_active', sa.Column('is_active', sa.Boolean(), nullable=True)),
        ])


def downgrade():
    for tbl in ('external_fact_checks', 'fact_check_sources', 'verification_results', 'claims', 'social_media_posts'):
        if _table_exists(tbl):
            op.drop_table(tbl)
