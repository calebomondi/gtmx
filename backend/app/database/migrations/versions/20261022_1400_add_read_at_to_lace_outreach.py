"""add_read_at_to_lace_outreach

When the founder opened a reply, so Messaging and Contacts can badge the
replies they have not read yet. Nullable: null is unread (outbound messages
never set it). A partial index serves the unread lookups.

Revision ID: effd0c6cdcb3
Revises: c427154b4559
Create Date: 2026-10-22 14:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "effd0c6cdcb3"
down_revision = "c427154b4559"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lace_outreach", sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_lace_outreach_unread", "lace_outreach", ["lace_id"],
                    postgresql_where=sa.text("direction = 'inbound' AND read_at IS NULL"))


def downgrade() -> None:
    op.drop_index("ix_lace_outreach_unread", table_name="lace_outreach",
                  postgresql_where=sa.text("direction = 'inbound' AND read_at IS NULL"))
    op.drop_column("lace_outreach", "read_at")
