"""add intent and meeting to outreach_messages

`intent` records how the GTM specialist read a reply; `meeting` holds the
meeting a reply draft proposes (added to Google Calendar only when the user
clicks). Both nullable: existing rows have neither.

Revision ID: 5d7e9a1c3b62
Revises: 3a9c5e7f1b24
Create Date: 2026-10-12 15:00:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '5d7e9a1c3b62'
down_revision: Union[str, Sequence[str], None] = '3a9c5e7f1b24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('outreach_messages', sa.Column('intent', sa.String(length=24), nullable=True))
    op.add_column('outreach_messages', sa.Column('meeting', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('outreach_messages', 'meeting')
    op.drop_column('outreach_messages', 'intent')
