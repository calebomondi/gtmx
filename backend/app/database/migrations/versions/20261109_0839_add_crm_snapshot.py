"""add_crm_snapshot

lace_crm_records: each Lace's copy of the founder's CRM (companies and people,
with where each stands: customer, open deal, lead, or just on file), refreshed
by a daily sync; laces.crm_synced_at for when. lace_accounts.crm_status and
crm_stage: where a lead stands in that CRM. Two more signal kinds that move a
lead's temperature: crm and history (earlier mail with them).

Revision ID: 2813c3246270
Revises: 5f1c2a9d8e47
Create Date: 2026-11-09 08:39:36.695907+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2813c3246270'
down_revision: Union[str, Sequence[str], None] = '5f1c2a9d8e47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('lace_crm_records',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('crm', sa.String(length=16), nullable=False),
    sa.Column('kind', sa.String(length=8), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('company', sa.String(length=255), nullable=True),
    sa.Column('email', sa.String(length=320), nullable=True),
    sa.Column('domain', sa.String(length=255), nullable=True),
    sa.Column('company_key', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('stage', sa.String(length=120), nullable=True),
    sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("crm IN ('zoho', 'hubspot')", name=op.f('ck_lace_crm_records_crm')),
    sa.CheckConstraint("kind IN ('company', 'person')", name=op.f('ck_lace_crm_records_kind')),
    sa.CheckConstraint("status IN ('customer', 'open_deal', 'lead', 'known')", name=op.f('ck_lace_crm_records_status')),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_crm_records_lace_id_laces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_crm_records'))
    )
    op.create_index('ix_lace_crm_records_lace_id_company_key', 'lace_crm_records', ['lace_id', 'company_key'], unique=False)
    op.create_index('ix_lace_crm_records_lace_id_domain', 'lace_crm_records', ['lace_id', 'domain'], unique=False)
    op.create_index('ix_lace_crm_records_lace_id_email', 'lace_crm_records', ['lace_id', 'email'], unique=False)
    op.add_column('lace_accounts', sa.Column('crm_status', sa.String(length=12), nullable=True))
    op.add_column('lace_accounts', sa.Column('crm_stage', sa.String(length=120), nullable=True))
    op.add_column('laces', sa.Column('crm_synced_at', sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(op.f('ck_lace_accounts_crm_status'), 'lace_accounts',
                               "crm_status IS NULL OR crm_status IN ('customer', 'open_deal', 'lead', 'known')")
    op.drop_constraint(op.f('ck_lace_account_signals_kind'), 'lace_account_signals', type_='check')
    op.create_check_constraint(op.f('ck_lace_account_signals_kind'), 'lace_account_signals',
                               "kind IN ('reply', 'meeting', 'customer', 'opt_out', 'cooled', 'crm', 'history')")


def downgrade() -> None:
    """Downgrade schema."""
    # Signals of the new kinds can't stay under the old check.
    op.execute("DELETE FROM lace_account_signals WHERE kind IN ('crm', 'history')")
    op.drop_constraint(op.f('ck_lace_account_signals_kind'), 'lace_account_signals', type_='check')
    op.create_check_constraint(op.f('ck_lace_account_signals_kind'), 'lace_account_signals',
                               "kind IN ('reply', 'meeting', 'customer', 'opt_out', 'cooled')")
    op.drop_constraint(op.f('ck_lace_accounts_crm_status'), 'lace_accounts', type_='check')
    op.drop_column('laces', 'crm_synced_at')
    op.drop_column('lace_accounts', 'crm_stage')
    op.drop_column('lace_accounts', 'crm_status')
    op.drop_index('ix_lace_crm_records_lace_id_email', table_name='lace_crm_records')
    op.drop_index('ix_lace_crm_records_lace_id_domain', table_name='lace_crm_records')
    op.drop_index('ix_lace_crm_records_lace_id_company_key', table_name='lace_crm_records')
    op.drop_table('lace_crm_records')
