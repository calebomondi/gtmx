"""allow social channels in lace outreach

Drafts can now go to an organisation's X, Instagram, Facebook or TikTok
account, so the channel check widens from email and LinkedIn to all six. The
downgrade first turns any such row back into a LinkedIn draft, so the
narrower check can be restored on a populated table.

Revision ID: 8f2a6c1d9e47
Revises: 3c7daecf3fdc
Create Date: 2026-10-18 20:30:00+00:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = '8f2a6c1d9e47'
down_revision: Union[str, Sequence[str], None] = '3c7daecf3fdc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ALL = "channel IN ('email', 'linkedin', 'x', 'instagram', 'facebook', 'tiktok')"
_BEFORE = "channel IN ('email', 'linkedin')"


def upgrade() -> None:
    op.drop_constraint(op.f('ck_lace_outreach_channel'), 'lace_outreach', type_='check')
    op.create_check_constraint(op.f('ck_lace_outreach_channel'), 'lace_outreach', _ALL)


def downgrade() -> None:
    op.execute("UPDATE lace_outreach SET channel = 'linkedin' WHERE channel NOT IN ('email', 'linkedin')")
    op.drop_constraint(op.f('ck_lace_outreach_channel'), 'lace_outreach', type_='check')
    op.create_check_constraint(op.f('ck_lace_outreach_channel'), 'lace_outreach', _BEFORE)
