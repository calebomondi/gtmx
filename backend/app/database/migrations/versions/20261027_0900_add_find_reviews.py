"""add_find_reviews

A member pushes their private finds to the team: lace_competitors,
lace_accounts and lace_opportunities gain proposed_at (waiting for review,
indexed for the team's "to review" list) and review_note (why one was sent
back). Feed items for a push and a send-back: 'finds_proposed',
'finds_returned'.

Revision ID: 6f1a3c8e2b57
Revises: 2c7e9a4d6b18
Create Date: 2026-10-27 09:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "6f1a3c8e2b57"
down_revision = "2c7e9a4d6b18"
branch_labels = None
depends_on = None

_TABLES = ("lace_competitors", "lace_accounts", "lace_opportunities")
_KINDS = ("'brief', 'competitors_found', 'competitor_moves', 'accounts_found', 'contacts_found', "
          "'drafts_ready', 'reply_received', 'opportunities_found', 'job_failed', 'app_action', 'access_requested', "
          "'comments_read', 'member_joined', 'message_sent', 'competitor_saved', 'account_saved', 'opportunity_saved'")
_NEW = ("finds_proposed", "finds_returned")


def _kinds(kinds: str) -> None:
    op.drop_constraint(op.f("ck_lace_activity_kind"), "lace_activity", type_="check")
    op.create_check_constraint(op.f("ck_lace_activity_kind"), "lace_activity", f"kind IN ({kinds})")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("review_note", sa.Text(), nullable=True))
        op.create_index(f"ix_{table}_proposed", table, ["lace_id"], postgresql_where=sa.text("proposed_at IS NOT NULL"))
    _kinds(_KINDS + "".join(f", '{k}'" for k in _NEW))


def downgrade() -> None:
    op.execute("DELETE FROM lace_activity WHERE kind IN (%s)" % ", ".join(f"'{k}'" for k in _NEW))
    _kinds(_KINDS)
    for table in _TABLES:
        op.drop_index(f"ix_{table}_proposed", table_name=table)
        op.drop_column(table, "review_note")
        op.drop_column(table, "proposed_at")
