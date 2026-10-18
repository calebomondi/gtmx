"""add lace tables

The first Lace v2 tables (docs/lace-plan.md): `laces`, one per startup agent;
`lace_facts`, what each Lace knows, superseded rather than overwritten;
`lace_sources`, the pages it read, one row per URL per Lace. New tables only;
the v1 schema is untouched.

Revision ID: a55b6e1927d9
Revises: 2c4e6a8b0d35
Create Date: 2026-10-17 22:12:33.215310+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a55b6e1927d9'
down_revision: Union[str, Sequence[str], None] = '2c4e6a8b0d35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('laces',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('website', sa.Text(), nullable=False),
    sa.Column('startup_name', sa.String(length=200), nullable=True),
    sa.Column('status', sa.String(length=16), server_default='onboarding', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('onboarding', 'active', 'archived')", name=op.f('ck_laces_status')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_laces'))
    )
    op.create_index(op.f('ix_laces_status'), 'laces', ['status'], unique=False)
    op.create_index(op.f('ix_laces_user_id'), 'laces', ['user_id'], unique=False)
    op.create_table('lace_facts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('topic', sa.String(length=24), nullable=False),
    sa.Column('claim', sa.Text(), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=True),
    sa.Column('confidence', sa.String(length=8), nullable=False),
    sa.Column('origin', sa.String(length=12), nullable=False),
    sa.Column('superseded_by_id', sa.UUID(), nullable=True),
    sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("confidence IN ('high', 'medium', 'low')", name=op.f('ck_lace_facts_confidence')),
    sa.CheckConstraint("origin IN ('crawl', 'research', 'user', 'monitor')", name=op.f('ck_lace_facts_origin')),
    sa.CheckConstraint("source_url IS NOT NULL OR origin = 'user'", name=op.f('ck_lace_facts_sourced')),
    sa.CheckConstraint("topic IN ('company', 'offer', 'pricing', 'customers', 'market', 'competition', 'icp', 'positioning')", name=op.f('ck_lace_facts_topic')),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_facts_lace_id_laces'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['superseded_by_id'], ['lace_facts.id'], name=op.f('fk_lace_facts_superseded_by_id_lace_facts'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_facts'))
    )
    op.create_index('ix_lace_facts_lace_id_topic', 'lace_facts', ['lace_id', 'topic'], unique=False)
    op.create_index(op.f('ix_lace_facts_recorded_at'), 'lace_facts', ['recorded_at'], unique=False)
    op.create_index(op.f('ix_lace_facts_superseded_by_id'), 'lace_facts', ['superseded_by_id'], unique=False)
    op.create_table('lace_sources',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('title', sa.Text(), server_default='', nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_sources_lace_id_laces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_sources')),
    sa.UniqueConstraint('lace_id', 'url', name='uq_lace_sources_lace_id_url')
    )


def downgrade() -> None:
    op.drop_table('lace_sources')
    op.drop_index(op.f('ix_lace_facts_superseded_by_id'), table_name='lace_facts')
    op.drop_index(op.f('ix_lace_facts_recorded_at'), table_name='lace_facts')
    op.drop_index('ix_lace_facts_lace_id_topic', table_name='lace_facts')
    op.drop_table('lace_facts')
    op.drop_index(op.f('ix_laces_user_id'), table_name='laces')
    op.drop_index(op.f('ix_laces_status'), table_name='laces')
    op.drop_table('laces')
