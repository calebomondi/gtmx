"""add_user_events

What users do in the customer app, from a fixed list of event names (a page
opened, a panel opened, a setup phase reached), for seeing how the app is
used and where people stop.

Revision ID: 2e9a6c4b8f31
Revises: 7c2f5a9e3d14
Create Date: 2026-10-27 13:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "2e9a6c4b8f31"
down_revision = "7c2f5a9e3d14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("lace_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=48), nullable=False),
        sa.Column("detail", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["lace_id"], ["laces.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_events_user_id", "user_events", ["user_id"])
    op.create_index("ix_user_events_lace_id", "user_events", ["lace_id"])
    op.create_index("ix_user_events_created_at", "user_events", ["created_at"])
    op.create_index("ix_user_events_name_created_at", "user_events", ["name", "created_at"])


def downgrade() -> None:
    op.drop_table("user_events")
