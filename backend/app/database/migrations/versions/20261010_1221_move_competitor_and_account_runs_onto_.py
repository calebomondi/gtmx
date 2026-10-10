"""move competitor and account runs onto runs

Revision ID: c67c08135dcc
Revises: 96ba21eb5dc4
Create Date: 2026-10-10 12:21:33.673300+00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c67c08135dcc'
down_revision: Union[str, Sequence[str], None] = '96ba21eb5dc4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Copy competitor/account run history into `runs` (same ids, counts into
    `progress`) and repoint competitors.run_id / accounts.run_id at runs.id.

    Expand step only: competitor_runs and account_runs are left in place,
    unused, and dropped by a later migration once no deployed code reads them.
    """
    op.execute("""
        INSERT INTO runs (id, user_id, workspace_id, kind, status, progress, error,
                          created_at, started_at, finished_at, updated_at)
        SELECT cr.id, w.user_id, cr.workspace_id, 'competitors', cr.status,
               jsonb_build_object(
                   'candidates_seen', cr.candidates_seen, 'found', cr.found,
                   'dropped', cr.dropped, 'dropped_reasons', cr.dropped_reasons,
                   'profile_confidence', cr.profile_confidence,
                   'archetypes_targeted', cr.archetypes_targeted),
               cr.error, cr.created_at, cr.started_at, cr.finished_at, now()
        FROM competitor_runs cr JOIN workspaces w ON w.id = cr.workspace_id
        ON CONFLICT (id) DO NOTHING
    """)
    op.execute("""
        INSERT INTO runs (id, user_id, workspace_id, kind, status, progress, error,
                          created_at, started_at, finished_at, updated_at)
        SELECT ar.id, w.user_id, ar.workspace_id, 'accounts', ar.status,
               jsonb_build_object('candidates_seen', ar.candidates_seen, 'found', ar.found),
               ar.error, ar.created_at, ar.started_at, ar.finished_at, now()
        FROM account_runs ar JOIN workspaces w ON w.id = ar.workspace_id
        ON CONFLICT (id) DO NOTHING
    """)
    op.drop_constraint("fk_competitors_run_id_competitor_runs", "competitors", type_="foreignkey")
    op.create_foreign_key(
        op.f("fk_competitors_run_id_runs"), "competitors", "runs", ["run_id"], ["id"], ondelete="SET NULL",
    )
    op.drop_constraint("fk_accounts_run_id_account_runs", "accounts", type_="foreignkey")
    op.create_foreign_key(
        op.f("fk_accounts_run_id_runs"), "accounts", "runs", ["run_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    """Point the FKs back at the legacy tables. Runs created after the upgrade
    have no legacy row, so their references are cleared first."""
    op.drop_constraint("fk_accounts_run_id_runs", "accounts", type_="foreignkey")
    op.drop_constraint("fk_competitors_run_id_runs", "competitors", type_="foreignkey")
    op.execute("UPDATE competitors SET run_id = NULL WHERE run_id NOT IN (SELECT id FROM competitor_runs)")
    op.execute("UPDATE accounts SET run_id = NULL WHERE run_id NOT IN (SELECT id FROM account_runs)")
    op.create_foreign_key(
        "fk_competitors_run_id_competitor_runs", "competitors", "competitor_runs", ["run_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_accounts_run_id_account_runs", "accounts", "account_runs", ["run_id"], ["id"], ondelete="SET NULL",
    )
    op.execute("DELETE FROM runs WHERE kind IN ('competitors', 'accounts', 'competitor_research')")
