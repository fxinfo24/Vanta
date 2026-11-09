"""Auth users table + per-user ownership columns

Revision ID: d1e2f3a4b5c6
Revises: c7d8e9f0a1b2
Create Date: 2026-11-08

Adds the `users` table (app/web/models/user.py, legacy declarative Base)
and `user_id` ownership columns on `task` and `social_media_posts` so
every /api route can scope data to the authenticated user. All new
columns are nullable: pre-auth rows stay readable by their owner only
after backfill; new rows are always stamped by the API.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'd1e2f3a4b5c6'
down_revision = 'c7d8e9f0a1b2'
branch_labels = None
depends_on = None


def _table_exists(name):
    return inspect(op.get_bind()).has_table(name)


def _add_column_if_missing(table, name, column):
    existing = {c['name'] for c in inspect(op.get_bind()).get_columns(table)}
    if name not in existing:
        op.add_column(table, column)


def upgrade():
    if not _table_exists('users'):
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('email', sa.String(255), nullable=False),
            sa.Column('username', sa.String(50), nullable=True),
            sa.Column('hashed_password', sa.String(255), nullable=False),
            sa.Column('first_name', sa.String(100), nullable=True),
            sa.Column('last_name', sa.String(100), nullable=True),
            sa.Column('company', sa.String(200), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('is_verified', sa.Boolean(), nullable=True),
            sa.Column('role', sa.String(20), nullable=True),
            sa.Column('subscription_status', sa.String(20), nullable=True),
            sa.Column('subscription_expires', sa.DateTime(), nullable=True),
            sa.Column('api_calls_count', sa.Integer(), nullable=True),
            sa.Column('api_calls_limit', sa.Integer(), nullable=True),
            sa.Column('api_calls_reset', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('last_login', sa.DateTime(), nullable=True),
            sa.Column('api_key', sa.String(64), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('email'),
            sa.UniqueConstraint('username'),
            sa.UniqueConstraint('api_key'),
        )
        op.create_index('ix_users_email', 'users', ['email'])
        op.create_index('ix_users_username', 'users', ['username'])

    if _table_exists('task'):
        _add_column_if_missing('task', 'user_id', sa.Column('user_id', sa.Integer(), nullable=True))
        op.create_index('ix_task_user_id', 'task', ['user_id'], unique=False)

    if _table_exists('social_media_posts'):
        _add_column_if_missing('social_media_posts', 'user_id', sa.Column('user_id', sa.Integer(), nullable=True))
        op.create_index('ix_social_media_posts_user_id', 'social_media_posts', ['user_id'], unique=False)

    if not _table_exists('user_settings'):
        op.create_table(
            'user_settings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('default_mode', sa.String(20), nullable=True),
            sa.Column('preferred_model', sa.String(120), nullable=True),
            # Fernet-encrypted JSON blob {env_var: key}; never plaintext.
            sa.Column('byok_keys_enc', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id'),
        )
        op.create_index('ix_user_settings_user_id', 'user_settings', ['user_id'])


def downgrade():
    if _table_exists('user_settings'):
        op.drop_table('user_settings')
    op.drop_index('ix_social_media_posts_user_id', table_name='social_media_posts')
    op.drop_column('social_media_posts', 'user_id')
    op.drop_index('ix_task_user_id', table_name='task')
    op.drop_column('task', 'user_id')
    op.drop_table('users')
