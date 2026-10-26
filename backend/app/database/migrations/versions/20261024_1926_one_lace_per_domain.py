"""one_lace_per_domain

One Lace per startup: each Lace's website domain, unique among Laces. The
domains of existing Laces are filled in by backfill_lace_domains. Also lets
someone ask to join a Lace (a lace_members row with status 'requested'), and
tells its people on the Feed (activity kind 'access_requested').

Revision ID: 5e2a9d4c7b13
Revises: 8b0d5c3e9a61
Create Date: 2026-10-24 19:26:00
"""

import sqlalchemy as sa
from alembic import op

revision = "5e2a9d4c7b13"
down_revision = "8b0d5c3e9a61"
branch_labels = None
depends_on = None

_KINDS = ("'brief', 'competitors_found', 'competitor_moves', 'accounts_found', 'contacts_found', "
          "'drafts_ready', 'reply_received', 'opportunities_found', 'job_failed', 'app_action'")
_STATUSES = "'invited', 'active', 'declined'"


def _checks(kinds: str, statuses: str) -> None:
    op.drop_constraint(op.f("ck_lace_activity_kind"), "lace_activity", type_="check")
    op.create_check_constraint(op.f("ck_lace_activity_kind"), "lace_activity", f"kind IN ({kinds})")
    op.drop_constraint(op.f("ck_lace_members_status"), "lace_members", type_="check")
    op.create_check_constraint(op.f("ck_lace_members_status"), "lace_members", f"status IN ({statuses})")


def upgrade() -> None:
    op.add_column("laces", sa.Column("domain", sa.String(length=255), nullable=True))
    op.create_index("uq_laces_domain", "laces", ["domain"], unique=True, postgresql_where=sa.text("domain IS NOT NULL"))
    _checks(f"{_KINDS}, 'access_requested'", f"{_STATUSES}, 'requested'")


def downgrade() -> None:
    op.execute("DELETE FROM lace_activity WHERE kind = 'access_requested'")
    op.execute("DELETE FROM lace_members WHERE status = 'requested'")
    _checks(_KINDS, _STATUSES)
    op.drop_index("uq_laces_domain", table_name="laces", postgresql_where=sa.text("domain IS NOT NULL"))
    op.drop_column("laces", "domain")
