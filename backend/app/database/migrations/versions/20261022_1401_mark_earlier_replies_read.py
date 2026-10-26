"""mark_earlier_replies_read

Replies that arrived before read state existed were already in front of the
founder; mark them read so they don't all light up as new. Data only, and
idempotent: it touches only replies from before this change that are still
unread. Downgrade leaves them read (the column itself goes with its own
migration).

Revision ID: 2525c2f736b2
Revises: effd0c6cdcb3
Create Date: 2026-10-22 14:01:00
"""

import sqlalchemy as sa
from alembic import op

revision = "2525c2f736b2"
down_revision = "effd0c6cdcb3"
branch_labels = None
depends_on = None

# Replies received before read state shipped.
_BEFORE = "2026-10-22 14:00:00+00"


def upgrade() -> None:
    op.execute(sa.text(
        "UPDATE lace_outreach SET read_at = created_at WHERE direction = 'inbound' AND read_at IS NULL"
        " AND created_at < CAST(:before AS timestamptz)").bindparams(before=_BEFORE))


def downgrade() -> None:
    pass
