"""add_comments_read_activity

A Feed item for a read of the comments on the founder's TikTok videos
(activity kind 'comments_read').

Revision ID: c41b8e2d6f90
Revises: a7c3e1f05d82
Create Date: 2026-10-25 12:00:00
"""

from alembic import op

revision = "c41b8e2d6f90"
down_revision = "a7c3e1f05d82"
branch_labels = None
depends_on = None

_KINDS = ("'brief', 'competitors_found', 'competitor_moves', 'accounts_found', 'contacts_found', "
          "'drafts_ready', 'reply_received', 'opportunities_found', 'job_failed', 'app_action', 'access_requested'")


def _kinds(kinds: str) -> None:
    op.drop_constraint(op.f("ck_lace_activity_kind"), "lace_activity", type_="check")
    op.create_check_constraint(op.f("ck_lace_activity_kind"), "lace_activity", f"kind IN ({kinds})")


def upgrade() -> None:
    _kinds(f"{_KINDS}, 'comments_read'")


def downgrade() -> None:
    op.execute("DELETE FROM lace_activity WHERE kind = 'comments_read'")
    _kinds(_KINDS)
