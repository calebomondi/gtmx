"""add review_status and via_competitor_id to accounts

A competitor's client is added as a *suggested* account the user accepts or
dismisses, so `review_status` (target | suggested | dismissed) defaults every
existing account to target. `via_competitor_id` links it to the competitor
that names it as a client; SET NULL if that competitor is removed.

Revision ID: 2c4e6a8b0d35
Revises: 8b3d5f7a9c14
Create Date: 2026-10-14 18:00:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2c4e6a8b0d35'
down_revision: Union[str, Sequence[str], None] = '8b3d5f7a9c14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('accounts', sa.Column('review_status', sa.String(length=16), server_default='target', nullable=False))
    op.add_column('accounts', sa.Column('via_competitor_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_accounts_review_status'), 'accounts', ['review_status'], unique=False)
    op.create_index(op.f('ix_accounts_via_competitor_id'), 'accounts', ['via_competitor_id'], unique=False)
    op.create_foreign_key(
        'fk_accounts_via_competitor_id_competitors', 'accounts', 'competitors',
        ['via_competitor_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_accounts_via_competitor_id_competitors', 'accounts', type_='foreignkey')
    op.drop_index(op.f('ix_accounts_via_competitor_id'), table_name='accounts')
    op.drop_index(op.f('ix_accounts_review_status'), table_name='accounts')
    op.drop_column('accounts', 'via_competitor_id')
    op.drop_column('accounts', 'review_status')
