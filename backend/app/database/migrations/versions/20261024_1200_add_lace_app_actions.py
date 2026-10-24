"""add_lace_app_actions

What a Lace proposes doing in its founder's apps (a post, a reply to a
comment, a lead), each waiting for the founder's click; and a Feed item kind
for when one runs.

Revision ID: cce3fb01ae3f
Revises: cba37e5de8cc
Create Date: 2026-10-24 12:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "cce3fb01ae3f"
down_revision = "cba37e5de8cc"
branch_labels = None
depends_on = None

_KINDS = ("'brief', 'competitors_found', 'competitor_moves', 'accounts_found', 'contacts_found', "
          "'drafts_ready', 'reply_received', 'opportunities_found', 'job_failed'")
_REFS = "'brief', 'outreach'"


def _activity_checks(kinds: str, refs: str) -> None:
    op.drop_constraint(op.f("ck_lace_activity_kind"), "lace_activity", type_="check")
    op.create_check_constraint(op.f("ck_lace_activity_kind"), "lace_activity", f"kind IN ({kinds})")
    op.drop_constraint(op.f("ck_lace_activity_ref_type"), "lace_activity", type_="check")
    op.create_check_constraint(op.f("ck_lace_activity_ref_type"), "lace_activity",
                               f"ref_type IS NULL OR ref_type IN ({refs})")


def upgrade() -> None:
    op.create_table(
        "lace_app_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lace_id", sa.UUID(), nullable=False),
        sa.Column("app", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("preview", sa.Text(), server_default="", nullable=False),
        sa.Column("arguments", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="proposed", nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("provider_log_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('proposed', 'running', 'done', 'failed', 'declined')",
                           name=op.f("ck_lace_app_actions_status")),
        sa.ForeignKeyConstraint(["lace_id"], ["laces.id"], name=op.f("fk_lace_app_actions_lace_id_laces"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lace_app_actions")),
    )
    op.create_index("ix_lace_app_actions_lace_id_status", "lace_app_actions", ["lace_id", "status"])
    op.create_index("ix_lace_app_actions_lace_id_created_at", "lace_app_actions", ["lace_id", "created_at"])
    _activity_checks(f"{_KINDS}, 'app_action'", f"{_REFS}, 'app_action'")


def downgrade() -> None:
    op.execute("DELETE FROM lace_activity WHERE kind = 'app_action' OR ref_type = 'app_action'")
    _activity_checks(_KINDS, _REFS)
    op.drop_index("ix_lace_app_actions_lace_id_created_at", table_name="lace_app_actions")
    op.drop_index("ix_lace_app_actions_lace_id_status", table_name="lace_app_actions")
    op.drop_table("lace_app_actions")
