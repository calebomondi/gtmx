"""add_private_chat_runs_and_events

A member's private chat with a Lace: runs.owner_id marks a run as working in
it (its turn, or a job that turn started), and lace_events.owner_id an update
for it. The one-turn-per-Lace index now counts the team's turns only; a
second allows one turn at a time in each member's private chat. NULL is the
team's (every existing row). No FKs: Supabase owns users.

Downgrade deletes the private updates and cancels unfinished private runs (the old
index would count them as the team's); finished ones keep their rows.

Revision ID: 2c7e9a4d6b18
Revises: 8b4d2f6e1a93
Create Date: 2026-10-26 18:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "2c7e9a4d6b18"
down_revision = "8b4d2f6e1a93"
branch_labels = None
depends_on = None

_ACTIVE = "status IN ('pending', 'running', 'awaiting_input')"
_TEAM_TURNS = f"lace_id IS NOT NULL AND kind IN ('lace_onboarding', 'lace_turn') AND {_ACTIVE}"


def upgrade() -> None:
    op.add_column("runs", sa.Column("owner_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_runs_owner_id"), "runs", ["owner_id"])
    op.drop_index("uq_runs_one_active_per_lace", table_name="runs")
    op.create_index("uq_runs_one_active_per_lace", "runs", ["lace_id"], unique=True,
                    postgresql_where=sa.text(_TEAM_TURNS.replace("lace_id IS NOT NULL", "lace_id IS NOT NULL AND owner_id IS NULL")))
    op.create_index("uq_runs_one_private_turn", "runs", ["lace_id", "owner_id"], unique=True,
                    postgresql_where=sa.text(f"owner_id IS NOT NULL AND kind = 'lace_turn' AND {_ACTIVE}"))

    op.add_column("lace_events", sa.Column("owner_id", sa.UUID(), nullable=True))
    op.drop_index("ix_lace_events_pending", table_name="lace_events")
    op.create_index("ix_lace_events_pending", "lace_events", ["lace_id", "owner_id", "created_at"],
                    postgresql_where=sa.text("consumed_at IS NULL"))


def downgrade() -> None:
    op.execute("DELETE FROM lace_events WHERE owner_id IS NOT NULL")
    op.drop_index("ix_lace_events_pending", table_name="lace_events")
    op.create_index("ix_lace_events_pending", "lace_events", ["lace_id", "created_at"],
                    postgresql_where=sa.text("consumed_at IS NULL"))
    op.drop_column("lace_events", "owner_id")

    # Unfinished private turns would clash with the team's under the old index.
    op.execute(f"UPDATE runs SET status = 'cancelled' WHERE owner_id IS NOT NULL AND {_ACTIVE}")
    op.drop_index("uq_runs_one_private_turn", table_name="runs")
    op.drop_index("uq_runs_one_active_per_lace", table_name="runs")
    op.create_index("uq_runs_one_active_per_lace", "runs", ["lace_id"], unique=True,
                    postgresql_where=sa.text(_TEAM_TURNS))
    op.drop_index(op.f("ix_runs_owner_id"), table_name="runs")
    op.drop_column("runs", "owner_id")
