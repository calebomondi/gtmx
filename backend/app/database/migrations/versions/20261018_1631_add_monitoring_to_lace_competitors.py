"""add monitoring to lace competitors

The monitor's baseline per competitor (an opaque blob) and when it was last
checked, which the scheduler sorts and filters on. Both nullable: a firm that
was never checked has neither.

Revision ID: 1d7e0d0e08ec
Revises: ac0806f05613
Create Date: 2026-10-18 16:31:32.462013+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '1d7e0d0e08ec'
down_revision: Union[str, Sequence[str], None] = 'ac0806f05613'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lace_competitors', sa.Column('monitor_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('lace_competitors', sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_lace_competitors_last_checked_at'), 'lace_competitors', ['last_checked_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lace_competitors_last_checked_at'), table_name='lace_competitors')
    op.drop_column('lace_competitors', 'last_checked_at')
    op.drop_column('lace_competitors', 'monitor_state')
