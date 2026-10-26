"""add_lace_members

The people on a Lace: its owner and the cofounders they invite, with a role
(owner, admin, member) and whether they accepted. Owners of existing Laces
are filled in by the next migration (backfill_lace_owners).

Revision ID: f4a72ea18f12
Revises: 3f1c9a7e2b54
Create Date: 2026-10-24 18:43:53
"""

import sqlalchemy as sa
from alembic import op

revision = "f4a72ea18f12"
down_revision = "3f1c9a7e2b54"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lace_members",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lace_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("invited_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member')", name=op.f("ck_lace_members_role")),
        sa.CheckConstraint("status IN ('invited', 'active', 'declined')", name=op.f("ck_lace_members_status")),
        sa.ForeignKeyConstraint(["lace_id"], ["laces.id"], name=op.f("fk_lace_members_lace_id_laces"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lace_members")),
        sa.UniqueConstraint("lace_id", "user_id", name="uq_lace_members_lace_id_user_id"),
    )
    op.create_index("ix_lace_members_user_id_status", "lace_members", ["user_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_lace_members_user_id_status", table_name="lace_members")
    op.drop_table("lace_members")
