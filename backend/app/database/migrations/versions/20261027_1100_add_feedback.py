"""add_feedback

Suggestions and problems users send from the app's feedback button: who,
the Lace they had open, the page, the text, and whether the team has read
it.

Revision ID: 4b8e1d6f2a95
Revises: 9d4b2f7a1c63
Create Date: 2026-10-27 11:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "4b8e1d6f2a95"
down_revision = "9d4b2f7a1c63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("lace_id", sa.UUID(), nullable=True),
        sa.Column("path", sa.String(length=512), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=8), server_default="new", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('new', 'read')", name="ck_feedback_status"),
        sa.ForeignKeyConstraint(["lace_id"], ["laces.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_index("ix_feedback_lace_id", "feedback", ["lace_id"])
    op.create_index("ix_feedback_status", "feedback", ["status"])
    op.create_index("ix_feedback_created_at", "feedback", ["created_at"])


def downgrade() -> None:
    op.drop_table("feedback")
