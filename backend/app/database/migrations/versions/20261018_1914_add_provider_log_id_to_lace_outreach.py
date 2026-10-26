"""add provider log id to lace outreach

Composio's log id for each send, kept for support as the workspace outreach
table does. Nullable: drafts have none.

Revision ID: 36abb908cb3b
Revises: 67e249f59c6f
Create Date: 2026-10-18 19:14:40.777355+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '36abb908cb3b'
down_revision: Union[str, Sequence[str], None] = '67e249f59c6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lace_outreach', sa.Column('provider_log_id', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('lace_outreach', 'provider_log_id')
