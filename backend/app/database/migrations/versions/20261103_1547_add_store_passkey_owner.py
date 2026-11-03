"""add_store_passkey_owner

A Store's owner signs with a passkey: its credential id, relying party and
origin, beside the public key the Store already had a column for.

Revision ID: bb7250d9a61a
Revises: 24286ff21378
Create Date: 2026-11-03 15:47:42.499342+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb7250d9a61a'
down_revision: Union[str, Sequence[str], None] = '24286ff21378'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('lace_stores', sa.Column('owner_credential_id', sa.String(length=512), nullable=True))
    op.add_column('lace_stores', sa.Column('owner_rp_id', sa.String(length=253), nullable=True))
    op.add_column('lace_stores', sa.Column('owner_origin', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('lace_stores', 'owner_origin')
    op.drop_column('lace_stores', 'owner_rp_id')
    op.drop_column('lace_stores', 'owner_credential_id')
