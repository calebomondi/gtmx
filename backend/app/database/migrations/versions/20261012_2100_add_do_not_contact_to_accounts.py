"""add do_not_contact to accounts

Set when someone at the account replies asking not to be contacted; drafting
and sending then refuse the account. Defaults to false for existing rows.

Revision ID: 7b9d1f3a5c24
Revises: 2c4e6a8b0d13
Create Date: 2026-10-12 21:00:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7b9d1f3a5c24'
down_revision: Union[str, Sequence[str], None] = '2c4e6a8b0d13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('accounts', sa.Column('do_not_contact', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column('accounts', 'do_not_contact')
