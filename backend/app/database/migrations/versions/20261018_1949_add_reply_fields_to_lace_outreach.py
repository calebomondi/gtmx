"""add reply fields to lace outreach

How an inbound reply was read (`lace_outreach.intent`), and whether someone at
an account asked not to be contacted (`lace_accounts.do_not_contact`, false by
default so existing rows stay contactable).

Revision ID: 3c7daecf3fdc
Revises: 36abb908cb3b
Create Date: 2026-10-18 19:49:54.353358+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3c7daecf3fdc'
down_revision: Union[str, Sequence[str], None] = '36abb908cb3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lace_accounts', sa.Column('do_not_contact', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('lace_outreach', sa.Column('intent', sa.String(length=24), nullable=True))


def downgrade() -> None:
    op.drop_column('lace_outreach', 'intent')
    op.drop_column('lace_accounts', 'do_not_contact')
