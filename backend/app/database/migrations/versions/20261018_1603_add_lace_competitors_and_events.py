"""add lace competitors and events

`lace_competitors`: real companies competing with a Lace's startup, one per
host per Lace, the sourced profile kept as an agent blob. `lace_events`: news
the Lace must pass on to its founder (a job finished), queued until its next
turn. The one-active-run index on `runs` now counts conversation runs only, so a
background hunt can run while the founder keeps chatting.

Revision ID: ac0806f05613
Revises: 6d1f0b3c8e24
Create Date: 2026-10-18 16:03:15.949450+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'ac0806f05613'
down_revision: Union[str, Sequence[str], None] = '6d1f0b3c8e24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_KINDS = "kind IN ('lace_onboarding', 'lace_turn') AND "
_CONVERSATION_ONLY = f"lace_id IS NOT NULL AND {_KINDS}status IN ('pending', 'running', 'awaiting_input')"


def _one_active_run_index(where: str) -> None:
    op.drop_index('uq_runs_one_active_per_lace', table_name='runs')
    op.create_index('uq_runs_one_active_per_lace', 'runs', ['lace_id'], unique=True,
                    postgresql_where=sa.text(where))


def upgrade() -> None:
    op.create_table('lace_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_events_lace_id_laces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_events'))
    )
    op.create_index(op.f('ix_lace_events_lace_id'), 'lace_events', ['lace_id'], unique=False)
    op.create_index('ix_lace_events_pending', 'lace_events', ['lace_id', 'created_at'], unique=False, postgresql_where=sa.text('consumed_at IS NULL'))
    op.create_table('lace_competitors',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('website', sa.Text(), nullable=False),
    sa.Column('domain_key', sa.String(length=255), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('profile', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('origin', sa.String(length=12), server_default='found', nullable=False),
    sa.Column('status', sa.String(length=12), server_default='tracked', nullable=False),
    sa.Column('found_by_run_id', sa.UUID(), nullable=True),
    sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("origin IN ('found', 'founder')", name=op.f('ck_lace_competitors_origin')),
    sa.CheckConstraint("status IN ('tracked', 'dismissed')", name=op.f('ck_lace_competitors_status')),
    sa.ForeignKeyConstraint(['found_by_run_id'], ['runs.id'], name=op.f('fk_lace_competitors_found_by_run_id_runs'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_competitors_lace_id_laces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_competitors')),
    sa.UniqueConstraint('lace_id', 'domain_key', name='uq_lace_competitors_lace_id_domain_key')
    )
    op.create_index(op.f('ix_lace_competitors_found_by_run_id'), 'lace_competitors', ['found_by_run_id'], unique=False)
    op.create_index('ix_lace_competitors_lace_id_status', 'lace_competitors', ['lace_id', 'status'], unique=False)
    op.create_index(op.f('ix_lace_competitors_last_seen_at'), 'lace_competitors', ['last_seen_at'], unique=False)
    _one_active_run_index(_CONVERSATION_ONLY)


def downgrade() -> None:
    _one_active_run_index(_CONVERSATION_ONLY.replace(_KINDS, ""))
    op.drop_index(op.f('ix_lace_competitors_last_seen_at'), table_name='lace_competitors')
    op.drop_index('ix_lace_competitors_lace_id_status', table_name='lace_competitors')
    op.drop_index(op.f('ix_lace_competitors_found_by_run_id'), table_name='lace_competitors')
    op.drop_table('lace_competitors')
    op.drop_index('ix_lace_events_pending', table_name='lace_events', postgresql_where=sa.text('consumed_at IS NULL'))
    op.drop_index(op.f('ix_lace_events_lace_id'), table_name='lace_events')
    op.drop_table('lace_events')
