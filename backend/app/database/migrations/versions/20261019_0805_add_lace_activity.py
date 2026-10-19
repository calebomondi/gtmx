"""add lace activity

What each Lace did or found, for the founder's Feed: kind, title, summary,
the one thing it is about (a reply, a brief), and when the founder saw it.

Revision ID: f7f02a2c956b
Revises: 430a5d7fe15e
Create Date: 2026-10-19 08:05:29.746074+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f7f02a2c956b'
down_revision: Union[str, Sequence[str], None] = '430a5d7fe15e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('lace_activity',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=24), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('ref_type', sa.String(length=16), nullable=True),
    sa.Column('ref_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("kind IN ('brief', 'competitors_found', 'competitor_moves', 'accounts_found', 'contacts_found', 'drafts_ready', 'reply_received', 'opportunities_found', 'job_failed')", name=op.f('ck_lace_activity_kind')),
    sa.CheckConstraint("ref_type IS NULL OR ref_type IN ('brief', 'outreach')", name=op.f('ck_lace_activity_ref_type')),
    sa.CheckConstraint('(ref_type IS NULL) = (ref_id IS NULL)', name=op.f('ck_lace_activity_ref_paired')),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_activity_lace_id_laces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_activity'))
    )
    op.create_index('ix_lace_activity_lace_id_created_at', 'lace_activity', ['lace_id', 'created_at'], unique=False)
    op.create_index('ix_lace_activity_unread', 'lace_activity', ['lace_id'], unique=False, postgresql_where=sa.text('read_at IS NULL'))


def downgrade() -> None:
    op.drop_index('ix_lace_activity_unread', table_name='lace_activity', postgresql_where=sa.text('read_at IS NULL'))
    op.drop_index('ix_lace_activity_lace_id_created_at', table_name='lace_activity')
    op.drop_table('lace_activity')
