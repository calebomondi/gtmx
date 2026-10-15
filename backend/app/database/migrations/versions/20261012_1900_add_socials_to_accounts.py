"""add socials to accounts

Account discovery finds and verifies each account's social pages, but they
were never stored, so an account kept for its socials reached the UI with no
way to contact it. NOT NULL with an empty-object default: existing rows get {}
until the next account run refreshes them.

Revision ID: 2c4e6a8b0d13
Revises: 9f1b3d5e7a80
Create Date: 2026-10-12 19:00:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '2c4e6a8b0d13'
down_revision: Union[str, Sequence[str], None] = '9f1b3d5e7a80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('accounts', sa.Column(
        'socials', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False,
    ))


def downgrade() -> None:
    op.drop_column('accounts', 'socials')
