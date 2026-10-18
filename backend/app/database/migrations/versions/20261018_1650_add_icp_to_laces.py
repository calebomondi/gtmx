"""add icp to laces

The Lace's ideal customer profile, its own judgment kept as one agent blob,
and when it was last defined. Both nullable: a new Lace has none yet.

Revision ID: dec6864434be
Revises: 1d7e0d0e08ec
Create Date: 2026-10-18 16:50:54.402927+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'dec6864434be'
down_revision: Union[str, Sequence[str], None] = '1d7e0d0e08ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('laces', sa.Column('icp', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('laces', sa.Column('icp_updated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('laces', 'icp_updated_at')
    op.drop_column('laces', 'icp')
