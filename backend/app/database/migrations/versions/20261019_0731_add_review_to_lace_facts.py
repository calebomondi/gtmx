"""add review to lace facts

The founder's review of what their Lace recorded: when they confirmed a fact,
or retracted it as wrong. Retracted facts leave what the Lace knows but stay
on record.

Revision ID: 430a5d7fe15e
Revises: 65bf58ddcca9
Create Date: 2026-10-19 07:31:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '430a5d7fe15e'
down_revision: Union[str, Sequence[str], None] = '65bf58ddcca9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lace_facts', sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('lace_facts', sa.Column('retracted_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_lace_facts_retracted_at'), 'lace_facts', ['retracted_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lace_facts_retracted_at'), table_name='lace_facts')
    op.drop_column('lace_facts', 'retracted_at')
    op.drop_column('lace_facts', 'confirmed_at')
