"""add_lace_apps

Which of its founder's connected apps each Lace may use, and that app's
settings for it. No rows to start with: a missing row is the default (channels
on everywhere; work apps on where switched on, or when there is one Lace).

Revision ID: 761ed96052bd
Revises: cce3fb01ae3f
Create Date: 2026-10-24 15:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "761ed96052bd"
down_revision = "cce3fb01ae3f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lace_apps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lace_id", sa.UUID(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["lace_id"], ["laces.id"], name=op.f("fk_lace_apps_lace_id_laces"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lace_apps")),
        sa.UniqueConstraint("lace_id", "platform", name="uq_lace_apps_lace_id_platform"),
    )


def downgrade() -> None:
    op.drop_table("lace_apps")
