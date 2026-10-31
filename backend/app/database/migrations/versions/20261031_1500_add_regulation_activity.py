"""add_regulation_activity

Feed items for the laws and regulations a search found ('regulations_found')
and for a tracked bill that moved through parliament ('bill_moved').

Revision ID: 5e2a9c7d1b43
Revises: af9c13656e82
Create Date: 2026-10-31 15:00:00
"""

from alembic import op

revision = "5e2a9c7d1b43"
down_revision = "af9c13656e82"
branch_labels = None
depends_on = None

_KINDS = ("'brief', 'competitors_found', 'competitor_moves', 'accounts_found', 'contacts_found', "
          "'drafts_ready', 'reply_received', 'opportunities_found', 'job_failed', 'app_action', 'access_requested', "
          "'comments_read', 'member_joined', 'message_sent', 'competitor_saved', 'account_saved', "
          "'opportunity_saved', 'finds_proposed', 'finds_returned'")


def _kinds(kinds: str) -> None:
    op.drop_constraint(op.f("ck_lace_activity_kind"), "lace_activity", type_="check")
    op.create_check_constraint(op.f("ck_lace_activity_kind"), "lace_activity", f"kind IN ({kinds})")


def upgrade() -> None:
    _kinds(f"{_KINDS}, 'regulations_found', 'bill_moved'")


def downgrade() -> None:
    op.execute("DELETE FROM lace_activity WHERE kind IN ('regulations_found', 'bill_moved')")
    _kinds(_KINDS)
