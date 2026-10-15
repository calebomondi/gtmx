"""add suggestions to chat_messages

The follow-up questions offered under an assistant answer, shown as chips the
user can click. An opaque UI hint (never filtered or joined on), so JSONB;
null for user messages and answers from before suggestions existed.

Revision ID: 4e8a2c6b1d97
Revises: 7b9d1f3a5c24
Create Date: 2026-10-13 03:30:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '4e8a2c6b1d97'
down_revision: Union[str, Sequence[str], None] = '7b9d1f3a5c24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('chat_messages', sa.Column('suggestions', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('chat_messages', 'suggestions')
