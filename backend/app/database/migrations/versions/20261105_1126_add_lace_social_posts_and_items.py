"""add_lace_social_posts_and_items

The founder's own posts with how they did, and what the Lace's listen kept
from comments and mentions (lead, question, feedback, praise) with where the
founder is with each: what the Social view shows.

Revision ID: 423e0cc70b11
Revises: 7cad625b0a52
Create Date: 2026-11-05 11:26:49.023407+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '423e0cc70b11'
down_revision: Union[str, Sequence[str], None] = '7cad625b0a52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('lace_social_posts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('platform', sa.String(length=16), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('text', sa.Text(), server_default='', nullable=False),
    sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('views', sa.Integer(), nullable=True),
    sa.Column('likes', sa.Integer(), nullable=True),
    sa.Column('comments', sa.Integer(), nullable=True),
    sa.Column('shares', sa.Integer(), nullable=True),
    sa.Column('read_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("platform IN ('x', 'instagram', 'facebook', 'tiktok', 'linkedin')", name=op.f('ck_lace_social_posts_platform')),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_social_posts_lace_id_laces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_social_posts')),
    sa.UniqueConstraint('lace_id', 'platform', 'url', name='uq_lace_social_posts_lace_id_platform_url')
    )
    op.create_index('ix_lace_social_posts_lace_id_posted_at', 'lace_social_posts', ['lace_id', 'posted_at'], unique=False)
    op.create_table('lace_social_items',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('platform', sa.String(length=16), nullable=False),
    sa.Column('key', sa.String(length=255), nullable=False),
    sa.Column('author', sa.String(length=255), nullable=True),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('url', sa.Text(), nullable=True),
    sa.Column('said_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('verdict', sa.String(length=12), nullable=False),
    sa.Column('note', sa.Text(), server_default='', nullable=False),
    sa.Column('status', sa.String(length=12), server_default='new', nullable=False),
    sa.Column('run_id', sa.UUID(), nullable=True),
    sa.Column('heard_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("platform IN ('x', 'instagram', 'facebook', 'tiktok', 'linkedin')", name=op.f('ck_lace_social_items_platform')),
    sa.CheckConstraint("status IN ('new', 'done', 'dismissed')", name=op.f('ck_lace_social_items_status')),
    sa.CheckConstraint("verdict IN ('lead', 'feedback', 'question', 'praise', 'noise')", name=op.f('ck_lace_social_items_verdict')),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_social_items_lace_id_laces'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], name=op.f('fk_lace_social_items_run_id_runs'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_social_items')),
    sa.UniqueConstraint('lace_id', 'platform', 'key', name='uq_lace_social_items_lace_id_platform_key')
    )
    op.create_index('ix_lace_social_items_lace_id_status_said_at', 'lace_social_items', ['lace_id', 'status', 'said_at'], unique=False)
    op.create_index(op.f('ix_lace_social_items_run_id'), 'lace_social_items', ['run_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lace_social_items_run_id'), table_name='lace_social_items')
    op.drop_index('ix_lace_social_items_lace_id_status_said_at', table_name='lace_social_items')
    op.drop_table('lace_social_items')
    op.drop_index('ix_lace_social_posts_lace_id_posted_at', table_name='lace_social_posts')
    op.drop_table('lace_social_posts')
