"""add pinned to laces

Whether the founder pinned the Lace to the top of their sidebar.

Revision ID: 65bf58ddcca9
Revises: d5945e86a886
Create Date: 2026-10-19 06:53:57.023782+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '65bf58ddcca9'
down_revision: Union[str, Sequence[str], None] = 'd5945e86a886'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('laces', sa.Column('pinned', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    op.drop_column('laces', 'pinned')
