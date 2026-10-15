"""backfill workspace offer_type

Fills workspaces.offer_type from the finished run's insights, else from the
offer_type the discovery run was started with. Only touches NULL rows, so it
is idempotent. downgrade() is a no-op: the column itself goes away with the
schema migration's downgrade.

Revision ID: 2b7c1e9d4f30
Revises: 970487c2d176
Create Date: 2026-10-11 19:50:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '2b7c1e9d4f30'
down_revision: Union[str, Sequence[str], None] = '970487c2d176'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE workspaces w
        SET offer_type = p.insights ->> 'offer_type'
        FROM product_profiles p
        WHERE p.workspace_id = w.id
          AND w.offer_type IS NULL
          AND p.insights ->> 'offer_type' IN ('product', 'service')
    """)
    op.execute("""
        UPDATE workspaces w
        SET offer_type = first_run.offer_type
        FROM (
            SELECT DISTINCT ON (workspace_id) workspace_id, input ->> 'offer_type' AS offer_type
            FROM runs
            WHERE kind = 'discovery' AND workspace_id IS NOT NULL
            ORDER BY workspace_id, created_at
        ) first_run
        WHERE first_run.workspace_id = w.id
          AND w.offer_type IS NULL
          AND first_run.offer_type IN ('product', 'service')
    """)


def downgrade() -> None:
    pass
