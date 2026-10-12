"""add reply threading to outreach_messages

Replies and bounces synced from the user's Gmail are stored beside what was
sent: `direction` tells them apart, `thread_id` ties them to the sent email,
`provider_message_id` stores each synced message once, and `read_at` tracks
unread replies. Existing rows are all outbound (server default).

Revision ID: 3a9c5e7f1b24
Revises: 8e2d4b1c7a50
Create Date: 2026-10-12 12:00:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3a9c5e7f1b24'
down_revision: Union[str, Sequence[str], None] = '8e2d4b1c7a50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('outreach_messages', sa.Column('direction', sa.String(length=8), server_default='outbound', nullable=False))
    op.add_column('outreach_messages', sa.Column('thread_id', sa.String(length=64), nullable=True))
    op.add_column('outreach_messages', sa.Column('provider_message_id', sa.String(length=128), nullable=True))
    op.add_column('outreach_messages', sa.Column('read_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_outreach_messages_thread_id'), 'outreach_messages', ['thread_id'], unique=False)
    op.create_check_constraint(
        'ck_outreach_messages_direction', 'outreach_messages', "direction IN ('outbound', 'inbound')",
    )
    op.create_unique_constraint(
        'uq_outreach_messages_user_provider_message', 'outreach_messages', ['user_id', 'provider_message_id'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_outreach_messages_user_provider_message', 'outreach_messages', type_='unique')
    op.drop_constraint('ck_outreach_messages_direction', 'outreach_messages', type_='check')
    op.drop_index(op.f('ix_outreach_messages_thread_id'), table_name='outreach_messages')
    op.drop_column('outreach_messages', 'read_at')
    op.drop_column('outreach_messages', 'provider_message_id')
    op.drop_column('outreach_messages', 'thread_id')
    op.drop_column('outreach_messages', 'direction')
