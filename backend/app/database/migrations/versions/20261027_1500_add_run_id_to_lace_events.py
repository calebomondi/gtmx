"""add_run_id_to_lace_events

The search a Lace update reports on, so the turn that passes the update on
can show the founder that search's new finds as cards.

Revision ID: 8b3d6f1a2c57
Revises: 5a1c7e3b9d42
Create Date: 2026-10-27 15:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "8b3d6f1a2c57"
down_revision = "5a1c7e3b9d42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lace_events", sa.Column("run_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_lace_events_run_id_runs", "lace_events", "runs", ["run_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_lace_events_run_id", "lace_events", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_lace_events_run_id", table_name="lace_events")
    op.drop_constraint("fk_lace_events_run_id_runs", "lace_events", type_="foreignkey")
    op.drop_column("lace_events", "run_id")
