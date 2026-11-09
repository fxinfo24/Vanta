"""password reset tokens

Revision ID: e3b7c1a94d20
Revises: bb4568e43fc8
Create Date: 2026-11-10 19:40:00.000000

One-time password reset tokens: the SHA-256 hash of the emailed token, its
expiry, and when it was used. Without this table the app has no way to reset a
forgotten password at all (only an authenticated change-password route).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e3b7c1a94d20'
down_revision = 'bb4568e43fc8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'password_reset_token',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('password_reset_token', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_password_reset_token_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_password_reset_token_token_hash'), ['token_hash'], unique=True)
        batch_op.create_index(batch_op.f('ix_password_reset_token_id'), ['id'], unique=False)


def downgrade():
    with op.batch_alter_table('password_reset_token', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_password_reset_token_id'))
        batch_op.drop_index(batch_op.f('ix_password_reset_token_token_hash'))
        batch_op.drop_index(batch_op.f('ix_password_reset_token_user_id'))
    op.drop_table('password_reset_token')
