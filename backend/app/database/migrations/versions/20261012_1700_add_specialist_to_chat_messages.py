"""add specialist_domain to chat_messages

Chat answers now come from one specialist (product, market, competition,
GTM); the column records who, so the conversation shows them. Nullable: the
user's messages and earlier answers have none.

Revision ID: 9f1b3d5e7a80
Revises: 5d7e9a1c3b62
Create Date: 2026-10-12 17:00:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9f1b3d5e7a80'
down_revision: Union[str, Sequence[str], None] = '5d7e9a1c3b62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('chat_messages', sa.Column('specialist_domain', sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column('chat_messages', 'specialist_domain')
