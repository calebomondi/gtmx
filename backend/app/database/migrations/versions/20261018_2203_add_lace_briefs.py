"""add lace briefs

A Lace's brief settings (how often, at what local hour, in which timezone,
daily at 08:00 UTC by default) and `lace_briefs`: each brief's digest and the
Lace's own words once posted in the conversation.

Revision ID: 3a7e3bb6af8c
Revises: ce399e4ae813
Create Date: 2026-10-18 22:03:51.887790+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3a7e3bb6af8c'
down_revision: Union[str, Sequence[str], None] = 'ce399e4ae813'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('lace_briefs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('digest', sa.Text(), nullable=False),
    sa.Column('body', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_briefs_lace_id_laces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_briefs'))
    )
    op.create_index('ix_lace_briefs_lace_id_created_at', 'lace_briefs', ['lace_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_lace_briefs_posted_at'), 'lace_briefs', ['posted_at'], unique=False)
    op.add_column('laces', sa.Column('brief_frequency', sa.String(length=8), server_default='daily', nullable=False))
    op.add_column('laces', sa.Column('brief_hour', sa.SmallInteger(), server_default='8', nullable=False))
    op.add_column('laces', sa.Column('timezone', sa.String(length=64), server_default='UTC', nullable=False))
    op.add_column('laces', sa.Column('last_brief_at', sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(op.f('ck_laces_brief_frequency'), 'laces', "brief_frequency IN ('off', 'daily', 'weekly')")
    op.create_check_constraint(op.f('ck_laces_brief_hour'), 'laces', "brief_hour BETWEEN 0 AND 23")


def downgrade() -> None:
    op.drop_constraint(op.f('ck_laces_brief_hour'), 'laces', type_='check')
    op.drop_constraint(op.f('ck_laces_brief_frequency'), 'laces', type_='check')
    op.drop_column('laces', 'last_brief_at')
    op.drop_column('laces', 'timezone')
    op.drop_column('laces', 'brief_hour')
    op.drop_column('laces', 'brief_frequency')
    op.drop_index(op.f('ix_lace_briefs_posted_at'), table_name='lace_briefs')
    op.drop_index('ix_lace_briefs_lace_id_created_at', table_name='lace_briefs')
    op.drop_table('lace_briefs')
