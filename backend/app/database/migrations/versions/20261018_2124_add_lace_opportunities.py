"""add lace opportunities

Places to showcase, buyers to sell to and partners found for a Lace's startup:
one per source page per Lace, with deadlines and event dates as real dates. A
new table only.

Revision ID: ce399e4ae813
Revises: f993ac69560c
Create Date: 2026-10-18 21:24:29.694242+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ce399e4ae813'
down_revision: Union[str, Sequence[str], None] = 'f993ac69560c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('lace_opportunities',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('organiser', sa.String(length=255), nullable=True),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('url_key', sa.String(length=1024), nullable=False),
    sa.Column('deadline', sa.Date(), nullable=True),
    sa.Column('event_date', sa.Date(), nullable=True),
    sa.Column('location', sa.String(length=255), nullable=True),
    sa.Column('why_it_fits', sa.Text(), server_default='', nullable=False),
    sa.Column('how_to_act', sa.Text(), server_default='', nullable=False),
    sa.Column('status', sa.String(length=12), server_default='open', nullable=False),
    sa.Column('found_by_run_id', sa.UUID(), nullable=True),
    sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('showcase', 'sell', 'partner')", name=op.f('ck_lace_opportunities_kind')),
    sa.CheckConstraint("status IN ('open', 'dismissed')", name=op.f('ck_lace_opportunities_status')),
    sa.ForeignKeyConstraint(['found_by_run_id'], ['runs.id'], name=op.f('fk_lace_opportunities_found_by_run_id_runs'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_opportunities_lace_id_laces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_opportunities')),
    sa.UniqueConstraint('lace_id', 'url_key', name='uq_lace_opportunities_lace_id_url_key')
    )
    op.create_index(op.f('ix_lace_opportunities_event_date'), 'lace_opportunities', ['event_date'], unique=False)
    op.create_index(op.f('ix_lace_opportunities_found_by_run_id'), 'lace_opportunities', ['found_by_run_id'], unique=False)
    op.create_index('ix_lace_opportunities_lace_id_status_deadline', 'lace_opportunities', ['lace_id', 'status', 'deadline'], unique=False)
    op.create_index(op.f('ix_lace_opportunities_last_seen_at'), 'lace_opportunities', ['last_seen_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lace_opportunities_last_seen_at'), table_name='lace_opportunities')
    op.drop_index('ix_lace_opportunities_lace_id_status_deadline', table_name='lace_opportunities')
    op.drop_index(op.f('ix_lace_opportunities_found_by_run_id'), table_name='lace_opportunities')
    op.drop_index(op.f('ix_lace_opportunities_event_date'), table_name='lace_opportunities')
    op.drop_table('lace_opportunities')
