"""add lace brief email

Emailing a Lace's brief to the founder (off by default), quiet hours in which
nothing is emailed (a local [start, end) window, both ends or neither), and
when each brief was emailed.

Revision ID: d5945e86a886
Revises: 3a7e3bb6af8c
Create Date: 2026-10-18 22:50:14.733263+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5945e86a886'
down_revision: Union[str, Sequence[str], None] = '3a7e3bb6af8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lace_briefs', sa.Column('emailed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_lace_briefs_emailed_at'), 'lace_briefs', ['emailed_at'], unique=False)
    op.add_column('laces', sa.Column('brief_email', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('laces', sa.Column('quiet_start', sa.SmallInteger(), nullable=True))
    op.add_column('laces', sa.Column('quiet_end', sa.SmallInteger(), nullable=True))
    op.create_check_constraint(op.f('ck_laces_quiet_hours_paired'), 'laces',
                               "(quiet_start IS NULL) = (quiet_end IS NULL)")
    op.create_check_constraint(op.f('ck_laces_quiet_hours_range'), 'laces',
                               "quiet_start BETWEEN 0 AND 23 AND quiet_end BETWEEN 0 AND 23 AND quiet_start <> quiet_end")


def downgrade() -> None:
    op.drop_constraint(op.f('ck_laces_quiet_hours_range'), 'laces', type_='check')
    op.drop_constraint(op.f('ck_laces_quiet_hours_paired'), 'laces', type_='check')
    op.drop_column('laces', 'quiet_end')
    op.drop_column('laces', 'quiet_start')
    op.drop_column('laces', 'brief_email')
    op.drop_index(op.f('ix_lace_briefs_emailed_at'), table_name='lace_briefs')
    op.drop_column('lace_briefs', 'emailed_at')
