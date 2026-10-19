"""add approved_at to lace contacts

When the founder cleared a contact for outreach. Drafts go only to approved
people; contacts on file before this start unapproved.

Revision ID: f0ed7a4d313e
Revises: 83be1868cf57
Create Date: 2026-10-19 12:33:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f0ed7a4d313e'
down_revision: Union[str, Sequence[str], None] = '83be1868cf57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lace_contacts', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_lace_contacts_approved_at'), 'lace_contacts', ['approved_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lace_contacts_approved_at'), table_name='lace_contacts')
    op.drop_column('lace_contacts', 'approved_at')
