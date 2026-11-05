"""add_mailbox_and_send_from

Which mailbox (gmail, outlook) each email went through, and the one a Lace
sends new email from when the founder picked. Both nullable: an email sent
before this has no mailbox recorded, and a Lace with none picked uses the first
connected.

Revision ID: 6b0be89f0f37
Revises: 423e0cc70b11
Create Date: 2026-11-05 16:47:23.226368+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b0be89f0f37'
down_revision: Union[str, Sequence[str], None] = '423e0cc70b11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MAILBOXES = "IN ('gmail', 'outlook')"


def upgrade() -> None:
    op.add_column('lace_outreach', sa.Column('mailbox', sa.String(length=16), nullable=True))
    op.create_check_constraint(op.f('ck_lace_outreach_mailbox'), 'lace_outreach', f"mailbox {_MAILBOXES}")
    op.add_column('laces', sa.Column('send_from', sa.String(length=16), nullable=True))
    op.create_check_constraint(op.f('ck_laces_send_from'), 'laces', f"send_from {_MAILBOXES}")


def downgrade() -> None:
    op.drop_constraint(op.f('ck_laces_send_from'), 'laces', type_='check')
    op.drop_column('laces', 'send_from')
    op.drop_constraint(op.f('ck_lace_outreach_mailbox'), 'lace_outreach', type_='check')
    op.drop_column('lace_outreach', 'mailbox')
