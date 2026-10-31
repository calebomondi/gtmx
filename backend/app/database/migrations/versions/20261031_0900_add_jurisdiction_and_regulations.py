"""add_jurisdiction_and_regulations

A Lace learns where its startup is registered and where it operates (ISO 3166
codes, confirmed by a founder), and keeps the laws, regulations, bills and
filing obligations that apply there in lace_regulations.

Revision ID: af9c13656e82
Revises: 3c7e9a2f5b18
Create Date: 2026-10-31 09:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "af9c13656e82"
down_revision = "3c7e9a2f5b18"
branch_labels = None
depends_on = None

_CODE = "^[A-Z]{2}(-[A-Z0-9]{1,3})?$"


def upgrade() -> None:
    op.add_column("laces", sa.Column("registered_in", sa.String(length=6), nullable=True))
    op.add_column("laces", sa.Column("operates_in", postgresql.ARRAY(sa.String(length=6)), server_default="{}",
                                     nullable=False))
    op.add_column("laces", sa.Column("jurisdiction_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(op.f("ck_laces_registered_in_code"), "laces", f"registered_in ~ '{_CODE}'")

    op.create_table(
        "lace_regulations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lace_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("authority", sa.String(length=255), nullable=True),
        sa.Column("jurisdiction", sa.String(length=6), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("url_key", sa.String(length=1024), nullable=False),
        sa.Column("stage", sa.String(length=16), nullable=True),
        sa.Column("stage_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("in_force_on", sa.Date(), nullable=True),
        sa.Column("next_date", sa.Date(), nullable=True),
        sa.Column("why_it_applies", sa.Text(), server_default="", nullable=False),
        sa.Column("what_to_do", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=12), server_default="suggested", nullable=False),
        sa.Column("found_by_run_id", sa.UUID(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_id", sa.UUID(), nullable=True),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("push_note", sa.Text(), nullable=True),
        sa.CheckConstraint(f"jurisdiction ~ '{_CODE}'", name=op.f("ck_lace_regulations_jurisdiction_code")),
        sa.CheckConstraint("kind IN ('law', 'regulation', 'bill', 'obligation')", name=op.f("ck_lace_regulations_kind")),
        sa.CheckConstraint(
            "stage IS NULL OR stage IN ('published', 'first_reading', 'committee', 'second_reading', 'whole_house', "
            "'third_reading', 'assented', 'withdrawn', 'lapsed')",
            name=op.f("ck_lace_regulations_stage")),
        sa.CheckConstraint("status IN ('suggested', 'tracked', 'dismissed')", name=op.f("ck_lace_regulations_status")),
        sa.ForeignKeyConstraint(["found_by_run_id"], ["runs.id"], name=op.f("fk_lace_regulations_found_by_run_id_runs"),
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lace_id"], ["laces.id"], name=op.f("fk_lace_regulations_lace_id_laces"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lace_regulations")),
        sa.UniqueConstraint("lace_id", "owner_id", "url_key", name="uq_lace_regulations_lace_id_owner_id_url_key",
                            postgresql_nulls_not_distinct=True),
    )
    op.create_index(op.f("ix_lace_regulations_found_by_run_id"), "lace_regulations", ["found_by_run_id"])
    op.create_index("ix_lace_regulations_lace_id_status_next_date", "lace_regulations",
                    ["lace_id", "status", "next_date"])
    op.create_index(op.f("ix_lace_regulations_last_seen_at"), "lace_regulations", ["last_seen_at"])
    op.create_index("ix_lace_regulations_proposed", "lace_regulations", ["lace_id"],
                    postgresql_where=sa.text("proposed_at IS NOT NULL"))
    op.create_index("ix_lace_regulations_status_last_checked_at", "lace_regulations", ["status", "last_checked_at"])


def downgrade() -> None:
    op.drop_index("ix_lace_regulations_status_last_checked_at", table_name="lace_regulations")
    op.drop_index("ix_lace_regulations_proposed", table_name="lace_regulations",
                  postgresql_where=sa.text("proposed_at IS NOT NULL"))
    op.drop_index(op.f("ix_lace_regulations_last_seen_at"), table_name="lace_regulations")
    op.drop_index("ix_lace_regulations_lace_id_status_next_date", table_name="lace_regulations")
    op.drop_index(op.f("ix_lace_regulations_found_by_run_id"), table_name="lace_regulations")
    op.drop_table("lace_regulations")

    op.drop_constraint(op.f("ck_laces_registered_in_code"), "laces", type_="check")
    op.drop_column("laces", "jurisdiction_confirmed_at")
    op.drop_column("laces", "operates_in")
    op.drop_column("laces", "registered_in")
