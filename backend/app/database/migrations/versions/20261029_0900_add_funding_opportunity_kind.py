"""add_funding_opportunity_kind

Opportunities gain a fourth kind, funding: grants, incubators, accelerators
and startup programmes the startup qualifies for.

Revision ID: 3c7e9a2f5b18
Revises: 8b3d6f1a2c57
Create Date: 2026-10-29 09:00:00
"""

from alembic import op

revision = "3c7e9a2f5b18"
down_revision = "8b3d6f1a2c57"
branch_labels = None
depends_on = None

_NAME = "ck_lace_opportunities_kind"


def upgrade() -> None:
    op.drop_constraint(op.f(_NAME), "lace_opportunities", type_="check")
    op.create_check_constraint(op.f(_NAME), "lace_opportunities", "kind IN ('showcase', 'sell', 'partner', 'funding')")


def downgrade() -> None:
    # The old constraint has no room for funding: those opportunities go.
    op.execute("DELETE FROM lace_opportunities WHERE kind = 'funding'")
    op.drop_constraint(op.f(_NAME), "lace_opportunities", type_="check")
    op.create_check_constraint(op.f(_NAME), "lace_opportunities", "kind IN ('showcase', 'sell', 'partner')")
