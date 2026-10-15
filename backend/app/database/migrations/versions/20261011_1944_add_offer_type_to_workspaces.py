"""add offer_type to workspaces

Product vs service, asserted at intake. Until now it lived only inside
product_profiles.insights JSON, which the admin console can't count on.
Nullable: existing rows are filled by the following data migration, and a
workspace whose run never recorded it stays NULL (unknown).

Revision ID: 970487c2d176
Revises: 4497d3f3a508
Create Date: 2026-10-11 19:44:36.593158+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '970487c2d176'
down_revision: Union[str, Sequence[str], None] = '4497d3f3a508'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workspaces', sa.Column('offer_type', sa.String(length=16), nullable=True))
    op.create_index(op.f('ix_workspaces_offer_type'), 'workspaces', ['offer_type'], unique=False)
    op.create_check_constraint(
        'ck_workspaces_offer_type', 'workspaces', "offer_type IN ('product', 'service')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_workspaces_offer_type', 'workspaces', type_='check')
    op.drop_index(op.f('ix_workspaces_offer_type'), table_name='workspaces')
    op.drop_column('workspaces', 'offer_type')
