"""add_actor_to_lace_activity

Who on a Lace's team did each Feed item or asked for it (lace_activity.actor_id,
no FK: Supabase owns users), and Feed items for what people on the team do:
'member_joined', 'message_sent', and one per kind of find saved.

Revision ID: 5e8a1b3c7d20
Revises: 9d2f6a1c3e47
Create Date: 2026-10-26 10:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "5e8a1b3c7d20"
down_revision = "9d2f6a1c3e47"
branch_labels = None
depends_on = None

_KINDS = ("'brief', 'competitors_found', 'competitor_moves', 'accounts_found', 'contacts_found', "
          "'drafts_ready', 'reply_received', 'opportunities_found', 'job_failed', 'app_action', 'access_requested', "
          "'comments_read'")
_NEW = ("member_joined", "message_sent", "competitor_saved", "account_saved", "opportunity_saved")


def _kinds(kinds: str) -> None:
    op.drop_constraint(op.f("ck_lace_activity_kind"), "lace_activity", type_="check")
    op.create_check_constraint(op.f("ck_lace_activity_kind"), "lace_activity", f"kind IN ({kinds})")


def upgrade() -> None:
    op.add_column("lace_activity", sa.Column("actor_id", sa.UUID(), nullable=True))
    _kinds(_KINDS + "".join(f", '{k}'" for k in _NEW))


def downgrade() -> None:
    op.execute("DELETE FROM lace_activity WHERE kind IN (%s)" % ", ".join(f"'{k}'" for k in _NEW))
    _kinds(_KINDS)
    op.drop_column("lace_activity", "actor_id")
