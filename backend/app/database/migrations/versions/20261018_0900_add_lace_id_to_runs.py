"""add lace_id to runs

Lace onboarding and turns run under the existing run manager, so a run can
belong to a Lace. Nullable: every v1 run has none. SET NULL on delete, because
a run is also the billing record of its LLM and API calls. A partial unique
index allows at most one unfinished run per Lace: its conversation is one
checkpoint thread, which takes one writer at a time.

Revision ID: 6d1f0b3c8e24
Revises: a55b6e1927d9
Create Date: 2026-10-18 09:00:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6d1f0b3c8e24'
down_revision: Union[str, Sequence[str], None] = 'a55b6e1927d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('runs', sa.Column('lace_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_runs_lace_id'), 'runs', ['lace_id'], unique=False)
    op.create_foreign_key(
        op.f('fk_runs_lace_id_laces'), 'runs', 'laces', ['lace_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index(
        'uq_runs_one_active_per_lace', 'runs', ['lace_id'], unique=True,
        postgresql_where=sa.text("lace_id IS NOT NULL AND status IN ('pending', 'running', 'awaiting_input')"),
    )


def downgrade() -> None:
    op.drop_index('uq_runs_one_active_per_lace', table_name='runs')
    op.drop_constraint(op.f('fk_runs_lace_id_laces'), 'runs', type_='foreignkey')
    op.drop_index(op.f('ix_runs_lace_id'), table_name='runs')
    op.drop_column('runs', 'lace_id')
