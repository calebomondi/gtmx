"""add lace outreach

A Lace's outreach messages: drafts it wrote, what the founder sent, and the
replies that came back, one row each, threaded by the provider's thread id.
A new table only.

Revision ID: 67e249f59c6f
Revises: c9bc4c43ab5a
Create Date: 2026-10-18 18:54:16.191403+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '67e249f59c6f'
down_revision: Union[str, Sequence[str], None] = 'c9bc4c43ab5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('lace_outreach',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('account_id', sa.UUID(), nullable=True),
    sa.Column('run_id', sa.UUID(), nullable=True),
    sa.Column('channel', sa.String(length=16), nullable=False),
    sa.Column('direction', sa.String(length=8), server_default='outbound', nullable=False),
    sa.Column('thread_id', sa.String(length=64), nullable=True),
    sa.Column('provider_message_id', sa.String(length=128), nullable=True),
    sa.Column('recipient_name', sa.String(length=255), nullable=True),
    sa.Column('recipient_company', sa.String(length=255), server_default='', nullable=False),
    sa.Column('recipient_address', sa.String(length=2048), nullable=True),
    sa.Column('subject', sa.String(length=255), nullable=True),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='draft', nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("channel IN ('email', 'linkedin')", name=op.f('ck_lace_outreach_channel')),
    sa.CheckConstraint("direction IN ('outbound', 'inbound')", name=op.f('ck_lace_outreach_direction')),
    sa.CheckConstraint("status IN ('draft', 'sending', 'sent', 'failed', 'bounced', 'received')", name=op.f('ck_lace_outreach_status')),
    sa.ForeignKeyConstraint(['account_id'], ['lace_accounts.id'], name=op.f('fk_lace_outreach_account_id_lace_accounts'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_outreach_lace_id_laces'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], name=op.f('fk_lace_outreach_run_id_runs'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_outreach'))
    )
    op.create_index(op.f('ix_lace_outreach_account_id'), 'lace_outreach', ['account_id'], unique=False)
    op.create_index('ix_lace_outreach_lace_id_status', 'lace_outreach', ['lace_id', 'status'], unique=False)
    op.create_index(op.f('ix_lace_outreach_run_id'), 'lace_outreach', ['run_id'], unique=False)
    op.create_index(op.f('ix_lace_outreach_sent_at'), 'lace_outreach', ['sent_at'], unique=False)
    op.create_index(op.f('ix_lace_outreach_thread_id'), 'lace_outreach', ['thread_id'], unique=False)
    op.create_index(op.f('ix_lace_outreach_user_id'), 'lace_outreach', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lace_outreach_user_id'), table_name='lace_outreach')
    op.drop_index(op.f('ix_lace_outreach_thread_id'), table_name='lace_outreach')
    op.drop_index(op.f('ix_lace_outreach_sent_at'), table_name='lace_outreach')
    op.drop_index(op.f('ix_lace_outreach_run_id'), table_name='lace_outreach')
    op.drop_index('ix_lace_outreach_lace_id_status', table_name='lace_outreach')
    op.drop_index(op.f('ix_lace_outreach_account_id'), table_name='lace_outreach')
    op.drop_table('lace_outreach')
