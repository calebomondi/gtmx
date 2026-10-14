"""add fit to accounts and insight to signals

`accounts.fit` holds why the offer suits the account now (need, capability,
payoff, angle); `signals.insight` holds what a feed item means for the user
and the move to make. Both are agent-written blobs nobody filters on, so
JSON; both nullable, filled as accounts are assessed and items are raised.

Revision ID: 8b3d5f7a9c14
Revises: 6a1c3e5b7d92
Create Date: 2026-10-14 15:00:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8b3d5f7a9c14'
down_revision: Union[str, Sequence[str], None] = '6a1c3e5b7d92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('accounts', sa.Column('fit', sa.JSON(), nullable=True))
    op.add_column('signals', sa.Column('insight', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('signals', 'insight')
    op.drop_column('accounts', 'fit')
