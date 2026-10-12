"""add summary to accounts

What the target does, in a sentence or two, for the account card. Nullable:
accounts found before this have none and the card falls back to industry and
size until the next account run refreshes them.

Revision ID: 6c1f0a2b9d37
Revises: 201d9b8547dd
Create Date: 2026-10-12 09:30:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6c1f0a2b9d37'
down_revision: Union[str, Sequence[str], None] = '201d9b8547dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('accounts', sa.Column('summary', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('accounts', 'summary')
