"""drop_pinned_from_laces

Pins are per person (lace_members.pinned, backfilled from this column), so
laces.pinned is no longer read. The downgrade brings it back with each
owner's pin.

Revision ID: 9d4b2f7a1c63
Revises: 6f1a3c8e2b57
Create Date: 2026-10-27 10:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "9d4b2f7a1c63"
down_revision = "6f1a3c8e2b57"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("laces", "pinned")


def downgrade() -> None:
    op.add_column("laces", sa.Column("pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.execute("""
        UPDATE laces SET pinned = m.pinned
        FROM lace_members m
        WHERE m.lace_id = laces.id AND m.user_id = laces.user_id AND m.role = 'owner'
    """)
