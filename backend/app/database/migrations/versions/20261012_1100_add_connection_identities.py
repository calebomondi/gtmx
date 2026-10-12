"""add connection_identities

The label (email, name, @handle) of each connected channel account, read once
from the provider. Composio stays the source of truth for the connection and
its tokens; this table holds no credentials.

Revision ID: 8e2d4b1c7a50
Revises: 6c1f0a2b9d37
Create Date: 2026-10-12 11:00:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8e2d4b1c7a50'
down_revision: Union[str, Sequence[str], None] = '6c1f0a2b9d37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'connection_identities',
        sa.Column('connection_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('platform', sa.String(length=32), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('connection_id', name=op.f('pk_connection_identities')),
    )
    op.create_index(op.f('ix_connection_identities_user_id'), 'connection_identities', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_connection_identities_user_id'), table_name='connection_identities')
    op.drop_table('connection_identities')
