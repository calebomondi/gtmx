"""add_lace_instructions

Standing instructions from a Lace's team on how it works, shown in its
prompt and read by the jobs they apply to.

Revision ID: 7cad625b0a52
Revises: 5e2a9c7d1b43
Create Date: 2026-11-04 13:24:36.089342+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7cad625b0a52'
down_revision: Union[str, Sequence[str], None] = '5e2a9c7d1b43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('lace_instructions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('text', sa.String(length=300), nullable=False),
    sa.Column('applies_to', sa.String(length=16), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("applies_to IN ('everything', 'competitors', 'leads', 'opportunities', 'outreach')", name=op.f('ck_lace_instructions_applies_to')),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_instructions_lace_id_laces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_instructions'))
    )
    op.create_index(op.f('ix_lace_instructions_created_by'), 'lace_instructions', ['created_by'], unique=False)
    op.create_index('ix_lace_instructions_lace_id_created_at', 'lace_instructions', ['lace_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_lace_instructions_lace_id_created_at', table_name='lace_instructions')
    op.drop_index(op.f('ix_lace_instructions_created_by'), table_name='lace_instructions')
    op.drop_table('lace_instructions')
