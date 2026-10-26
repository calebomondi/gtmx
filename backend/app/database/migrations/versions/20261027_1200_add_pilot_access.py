"""add_pilot_access

The closed pilot's guest list: emails an admin let in, typed in or approved
from the waitlist, and by whom.

Revision ID: 7c2f5a9e3d14
Revises: 4b8e1d6f2a95
Create Date: 2026-10-27 12:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "7c2f5a9e3d14"
down_revision = "4b8e1d6f2a95"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pilot_access",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("granted_by", sa.UUID(), nullable=True),
        sa.Column("granted_by_email", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source IN ('admin', 'waitlist')", name="ck_pilot_access_source"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_pilot_access_created_at", "pilot_access", ["created_at"])


def downgrade() -> None:
    op.drop_table("pilot_access")
