"""add_leads_sheet_fields_to_lace_accounts

What the founder wrote about a lead in their leads sheet, and its Status
there when last read. Both nullable: no backfill.

Revision ID: c1c53cbd8bfd
Revises: ca172a967b22
Create Date: 2026-11-10 08:11:38.966567+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1c53cbd8bfd'
down_revision: Union[str, Sequence[str], None] = 'ca172a967b22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('lace_accounts', sa.Column('founder_notes', sa.Text(), nullable=True))
    op.add_column('lace_accounts', sa.Column('sheet_status', sa.String(length=40), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('lace_accounts', 'sheet_status')
    op.drop_column('lace_accounts', 'founder_notes')
