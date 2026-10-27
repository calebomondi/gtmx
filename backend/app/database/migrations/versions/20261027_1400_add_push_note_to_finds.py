"""add_push_note_to_finds

A member's note to the reviewer on a private find they push to the team
(competitors, accounts, opportunities).

Revision ID: 5a1c7e3b9d42
Revises: 2e9a6c4b8f31
Create Date: 2026-10-27 14:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "5a1c7e3b9d42"
down_revision = "2e9a6c4b8f31"
branch_labels = None
depends_on = None

_TABLES = ("lace_competitors", "lace_accounts", "lace_opportunities")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("push_note", sa.Text(), nullable=True))


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "push_note")
