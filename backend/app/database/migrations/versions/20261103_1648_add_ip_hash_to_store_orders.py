"""add_ip_hash_to_store_orders

A salted hash of each buyer's IP, so public checkouts can be rate limited.

Revision ID: d49e2f95d8a8
Revises: bb7250d9a61a
Create Date: 2026-11-03 16:48:36.863150+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd49e2f95d8a8'
down_revision: Union[str, Sequence[str], None] = 'bb7250d9a61a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('store_orders', sa.Column('ip_hash', sa.String(length=64), nullable=True))
    op.create_index('ix_store_orders_ip_hash_created_at', 'store_orders', ['ip_hash', 'created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_store_orders_ip_hash_created_at', table_name='store_orders')
    op.drop_column('store_orders', 'ip_hash')
