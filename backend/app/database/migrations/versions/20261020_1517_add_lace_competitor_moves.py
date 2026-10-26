"""Add lace_competitor_moves: each material move a tracked competitor made

Revision ID: c202a1ec964a
Revises: d48d67751da3
Create Date: 2026-10-20 15:17:23.519857+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c202a1ec964a'
down_revision: Union[str, Sequence[str], None] = 'd48d67751da3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('lace_competitor_moves',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('competitor_id', sa.UUID(), nullable=False),
    sa.Column('run_id', sa.UUID(), nullable=True),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('importance', sa.String(length=8), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('implication', sa.Text(), nullable=True),
    sa.Column('counter_move', sa.Text(), nullable=True),
    sa.Column('sources', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("importance IN ('high', 'medium', 'low')", name=op.f('ck_lace_competitor_moves_importance')),
    sa.CheckConstraint("kind IN ('pricing', 'product', 'positioning', 'funding', 'leadership', 'partnership', 'event', 'social', 'news', 'client')", name=op.f('ck_lace_competitor_moves_kind')),
    sa.ForeignKeyConstraint(['competitor_id'], ['lace_competitors.id'], name=op.f('fk_lace_competitor_moves_competitor_id_lace_competitors'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_competitor_moves_lace_id_laces'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], name=op.f('fk_lace_competitor_moves_run_id_runs'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_competitor_moves'))
    )
    op.create_index('ix_lace_competitor_moves_competitor_id_detected_at', 'lace_competitor_moves', ['competitor_id', 'detected_at'], unique=False)
    op.create_index('ix_lace_competitor_moves_lace_id_detected_at', 'lace_competitor_moves', ['lace_id', 'detected_at'], unique=False)
    op.create_index(op.f('ix_lace_competitor_moves_run_id'), 'lace_competitor_moves', ['run_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_lace_competitor_moves_run_id'), table_name='lace_competitor_moves')
    op.drop_index('ix_lace_competitor_moves_lace_id_detected_at', table_name='lace_competitor_moves')
    op.drop_index('ix_lace_competitor_moves_competitor_id_detected_at', table_name='lace_competitor_moves')
    op.drop_table('lace_competitor_moves')
