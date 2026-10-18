"""add contact status to lace accounts

Whether a named person at the account can be reached (person, organisation
or none), and when its contacts were last searched for. Both nullable: an
account found before this change has neither until it is searched.

Revision ID: c9bc4c43ab5a
Revises: c48c5ae17cfd
Create Date: 2026-10-18 17:58:05.168689+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9bc4c43ab5a'
down_revision: Union[str, Sequence[str], None] = 'c48c5ae17cfd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lace_accounts', sa.Column('contact_status', sa.String(length=16), nullable=True))
    op.add_column('lace_accounts', sa.Column('contacts_checked_at', sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        op.f('ck_lace_accounts_contact_status'), 'lace_accounts',
        "contact_status IS NULL OR contact_status IN ('person', 'organisation', 'none')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f('ck_lace_accounts_contact_status'), 'lace_accounts', type_='check')
    op.drop_column('lace_accounts', 'contacts_checked_at')
    op.drop_column('lace_accounts', 'contact_status')
