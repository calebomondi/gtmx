"""add lace channels

A founder's Instagram business account or Facebook Page, linked to the Lace
that reads its inbound DMs: one Lace per account. A new table only.

Revision ID: f993ac69560c
Revises: 8f2a6c1d9e47
Create Date: 2026-10-18 20:56:11.918220+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f993ac69560c'
down_revision: Union[str, Sequence[str], None] = '8f2a6c1d9e47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('lace_channels',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('platform', sa.String(length=16), nullable=False),
    sa.Column('account_id', sa.String(length=64), nullable=False),
    sa.Column('account_name', sa.String(length=255), server_default='', nullable=False),
    sa.Column('synced_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("platform IN ('instagram', 'facebook')", name=op.f('ck_lace_channels_platform')),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_channels_lace_id_laces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_channels')),
    sa.UniqueConstraint('platform', 'account_id', name='uq_lace_channels_platform_account_id')
    )
    op.create_index(op.f('ix_lace_channels_lace_id'), 'lace_channels', ['lace_id'], unique=False)
    op.create_index(op.f('ix_lace_channels_user_id'), 'lace_channels', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lace_channels_user_id'), table_name='lace_channels')
    op.drop_index(op.f('ix_lace_channels_lace_id'), table_name='lace_channels')
    op.drop_table('lace_channels')
