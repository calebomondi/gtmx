"""add lace contacts

The people at each Lace's target accounts as rows: one per person per Lace,
keyed by email, else LinkedIn URL, else name. Rows already in account records
are backfilled by a separate data migration.

Revision ID: ffc4d9799974
Revises: f7f02a2c956b
Create Date: 2026-10-19 09:03:25.066653+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ffc4d9799974'
down_revision: Union[str, Sequence[str], None] = 'f7f02a2c956b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('lace_contacts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('account_id', sa.UUID(), nullable=False),
    sa.Column('key', sa.String(length=320), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=True),
    sa.Column('email', sa.String(length=320), nullable=True),
    sa.Column('linkedin', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=16), nullable=False),
    sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("source IN ('discovery', 'contact_search')", name=op.f('ck_lace_contacts_source')),
    sa.CheckConstraint('email IS NOT NULL OR linkedin IS NOT NULL OR name IS NOT NULL', name=op.f('ck_lace_contacts_identified')),
    sa.ForeignKeyConstraint(['account_id'], ['lace_accounts.id'], name=op.f('fk_lace_contacts_account_id_lace_accounts'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_contacts_lace_id_laces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_contacts')),
    sa.UniqueConstraint('lace_id', 'key', name='uq_lace_contacts_lace_id_key')
    )
    op.create_index(op.f('ix_lace_contacts_account_id'), 'lace_contacts', ['account_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lace_contacts_account_id'), table_name='lace_contacts')
    op.drop_table('lace_contacts')
