"""dossier snapshots and cross-platform profiles

Revision ID: bb4568e43fc8
Revises: d1e2f3a4b5c6
Create Date: 2026-11-10 00:03:35.896748

The two dossier tables were only ever created by `db.create_all()`, so a
database built from migrations never had them - which is why the snapshot
history feature worked locally and would have failed on a managed Postgres.

Autogenerate produced a destructive script alongside these two tables: it
dropped `users`/`user_settings` (their models live on the legacy declarative
Base, which is not in `db.metadata`), dropped the task listing indexes, and
downgraded every JSONB column to JSON. Those changes are not wanted, so this
migration only creates what is missing.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'bb4568e43fc8'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'cross_platform_profile',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('identity_name', sa.String(length=255), nullable=True),
        sa.Column('platforms', sa.JSON(), nullable=True),
        sa.Column('potential_links', sa.JSON(), nullable=True),
        sa.Column('total_followers', sa.Integer(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'dossier_snapshot',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('snapshot_data', sa.JSON(), nullable=True),
        sa.Column('analysis_data', sa.JSON(), nullable=True),
        sa.Column('collection_mode', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('summary_text', sa.Text(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('embedding_json', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['task.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_dossier_snapshot_task_id'), 'dossier_snapshot', ['task_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_dossier_snapshot_task_id'), table_name='dossier_snapshot')
    op.drop_table('dossier_snapshot')
    op.drop_table('cross_platform_profile')
