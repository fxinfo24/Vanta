"""provider balance key fingerprint

Revision ID: a7c9e14f2b83
Revises: f4c8d2e15b31
Create Date: 2026-11-10 21:05:00.000000

A provider balance belongs to one provider account. Storing it without
knowing which key produced it meant that a key change (top-up on a new
account, rotation) left a stale zero behind that blocked every run even
though the new key was funded.

The column holds a truncated SHA-256 of the key, never the key itself.
Balances recorded before this migration have no fingerprint, so they are
treated as applicable only until the next collection refreshes them.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a7c9e14f2b83'
down_revision = 'f4c8d2e15b31'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'provider_credit_usage',
        sa.Column('key_fingerprint', sa.String(length=32), nullable=True),
    )


def downgrade():
    op.drop_column('provider_credit_usage', 'key_fingerprint')
