"""add lace accounts

Target accounts for a Lace's startup: one per domain (or name, when it has no
site) per Lace, with the columns sorted and filtered on, and discovery's
record and the fit case as agent blobs. A new table only.

Revision ID: c48c5ae17cfd
Revises: dec6864434be
Create Date: 2026-10-18 17:03:53.136882+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c48c5ae17cfd'
down_revision: Union[str, Sequence[str], None] = 'dec6864434be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('lace_accounts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('key', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('account_type', sa.String(length=16), nullable=False),
    sa.Column('website', sa.Text(), nullable=True),
    sa.Column('geo', sa.String(length=120), nullable=True),
    sa.Column('score', sa.Float(), nullable=True),
    sa.Column('fit_strength', sa.String(length=12), nullable=True),
    sa.Column('status', sa.String(length=12), server_default='target', nullable=False),
    sa.Column('record', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('fit', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('found_by_run_id', sa.UUID(), nullable=True),
    sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("fit_strength IS NULL OR fit_strength IN ('strong', 'moderate', 'weak')", name=op.f('ck_lace_accounts_fit_strength')),
    sa.CheckConstraint("status IN ('target', 'dismissed')", name=op.f('ck_lace_accounts_status')),
    sa.ForeignKeyConstraint(['found_by_run_id'], ['runs.id'], name=op.f('fk_lace_accounts_found_by_run_id_runs'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_accounts_lace_id_laces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_accounts')),
    sa.UniqueConstraint('lace_id', 'key', name='uq_lace_accounts_lace_id_key')
    )
    op.create_index(op.f('ix_lace_accounts_found_by_run_id'), 'lace_accounts', ['found_by_run_id'], unique=False)
    op.create_index('ix_lace_accounts_lace_id_status', 'lace_accounts', ['lace_id', 'status'], unique=False)
    op.create_index(op.f('ix_lace_accounts_last_seen_at'), 'lace_accounts', ['last_seen_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lace_accounts_last_seen_at'), table_name='lace_accounts')
    op.drop_index('ix_lace_accounts_lace_id_status', table_name='lace_accounts')
    op.drop_index(op.f('ix_lace_accounts_found_by_run_id'), table_name='lace_accounts')
    op.drop_table('lace_accounts')
