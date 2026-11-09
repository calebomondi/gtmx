"""add_lead_temperature

A lead's temperature (cold, warm, hot, customer), why and since when, and when
a "not now" ends, on lace_accounts; and lace_account_signals, the history of
what moved it. Existing leads start cold; 20261109_0751 fills in the ones whose
replies already say otherwise.

Revision ID: e33fc680e1ad
Revises: 6b0be89f0f37
Create Date: 2026-11-09 07:50:06.880837+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e33fc680e1ad'
down_revision: Union[str, Sequence[str], None] = '6b0be89f0f37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('lace_account_signals',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('account_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('detail', sa.Text(), nullable=False),
    sa.Column('outreach_id', sa.UUID(), nullable=True),
    sa.Column('before', sa.String(length=12), nullable=True),
    sa.Column('after', sa.String(length=12), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("after IN ('cold', 'warm', 'hot', 'customer')", name=op.f('ck_lace_account_signals_after')),
    sa.CheckConstraint("before IS NULL OR before IN ('cold', 'warm', 'hot', 'customer')", name=op.f('ck_lace_account_signals_before')),
    sa.CheckConstraint("kind IN ('reply', 'meeting', 'customer', 'opt_out', 'cooled')", name=op.f('ck_lace_account_signals_kind')),
    sa.ForeignKeyConstraint(['account_id'], ['lace_accounts.id'], name=op.f('fk_lace_account_signals_account_id_lace_accounts'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_account_signals_lace_id_laces'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['outreach_id'], ['lace_outreach.id'], name=op.f('fk_lace_account_signals_outreach_id_lace_outreach'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_account_signals'))
    )
    op.create_index('ix_lace_account_signals_account_id_at', 'lace_account_signals', ['account_id', 'at'], unique=False)
    op.create_index(op.f('ix_lace_account_signals_lace_id'), 'lace_account_signals', ['lace_id'], unique=False)
    op.create_index(op.f('ix_lace_account_signals_outreach_id'), 'lace_account_signals', ['outreach_id'], unique=False)
    op.add_column('lace_accounts', sa.Column('temperature', sa.String(length=12), server_default='cold', nullable=False))
    op.add_column('lace_accounts', sa.Column('temperature_reason', sa.Text(), nullable=True))
    op.add_column('lace_accounts', sa.Column('temperature_changed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('lace_accounts', sa.Column('snoozed_until', sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(op.f('ck_lace_accounts_temperature'), 'lace_accounts',
                               "temperature IN ('cold', 'warm', 'hot', 'customer')")
    op.create_index('ix_lace_accounts_lace_id_temperature', 'lace_accounts', ['lace_id', 'temperature'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_lace_accounts_lace_id_temperature', table_name='lace_accounts')
    op.drop_constraint(op.f('ck_lace_accounts_temperature'), 'lace_accounts', type_='check')
    op.drop_column('lace_accounts', 'snoozed_until')
    op.drop_column('lace_accounts', 'temperature_changed_at')
    op.drop_column('lace_accounts', 'temperature_reason')
    op.drop_column('lace_accounts', 'temperature')
    op.drop_index(op.f('ix_lace_account_signals_outreach_id'), table_name='lace_account_signals')
    op.drop_index(op.f('ix_lace_account_signals_lace_id'), table_name='lace_account_signals')
    op.drop_index('ix_lace_account_signals_account_id_at', table_name='lace_account_signals')
    op.drop_table('lace_account_signals')
