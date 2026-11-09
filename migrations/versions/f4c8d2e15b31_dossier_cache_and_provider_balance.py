"""dossier cache and persisted provider balance

Revision ID: f4c8d2e15b31
Revises: e3b7c1a94d20
Create Date: 2026-11-10 20:40:00.000000

Two tables that existed only as local state before:

- `dossier_cache` holds the last collected raw dossier per (user, platform,
  profile) so re-analysis and regeneration reuse it instead of spending another
  ~14 provider credits.
- `provider_credit_usage` holds the last balance the provider reported. It was
  kept in a JSON file beside the code, which no deployed instance ever saw, so
  the pre-flight guard always saw "unknown" and could not block a run the
  balance could not cover.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f4c8d2e15b31'
down_revision = 'e3b7c1a94d20'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'dossier_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('profile_id', sa.String(length=255), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('collected_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'platform', 'profile_id', name='uq_dossier_cache_key'),
    )
    with op.batch_alter_table('dossier_cache', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_dossier_cache_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_dossier_cache_expires_at'), ['expires_at'], unique=False)

    op.create_table(
        'provider_credit_usage',
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('credits_remaining', sa.Integer(), nullable=True),
        sa.Column('observed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('provider'),
    )


def downgrade():
    op.drop_table('provider_credit_usage')
    with op.batch_alter_table('dossier_cache', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_dossier_cache_expires_at'))
        batch_op.drop_index(batch_op.f('ix_dossier_cache_user_id'))
    op.drop_table('dossier_cache')
