"""add_follow_up_sequence

lace_outreach.sequence_step (0 the first email, 1 and 2 its follow-ups) and
follow_up_due_at (when a sent email's follow-up is due if nobody answers),
with a partial index for the sweep that drafts the due ones. Emails already
sent get no due date: follow-ups start with the next ones sent.

Revision ID: ca172a967b22
Revises: 2813c3246270
Create Date: 2026-11-09 10:55:18.890542+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca172a967b22'
down_revision: Union[str, Sequence[str], None] = '2813c3246270'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('lace_outreach', sa.Column('sequence_step', sa.SmallInteger(), server_default='0', nullable=False))
    op.add_column('lace_outreach', sa.Column('follow_up_due_at', sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(op.f('ck_lace_outreach_sequence_step'), 'lace_outreach', 'sequence_step BETWEEN 0 AND 2')
    op.create_index('ix_lace_outreach_follow_up_due_at', 'lace_outreach', ['follow_up_due_at'], unique=False, postgresql_where=sa.text('follow_up_due_at IS NOT NULL'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f('ck_lace_outreach_sequence_step'), 'lace_outreach', type_='check')
    op.drop_index('ix_lace_outreach_follow_up_due_at', table_name='lace_outreach', postgresql_where=sa.text('follow_up_due_at IS NOT NULL'))
    op.drop_column('lace_outreach', 'follow_up_due_at')
    op.drop_column('lace_outreach', 'sequence_step')
