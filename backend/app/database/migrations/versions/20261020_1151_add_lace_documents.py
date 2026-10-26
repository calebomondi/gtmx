"""Add lace_documents: what founders share with their Lace, as text

Revision ID: d48d67751da3
Revises: f0ed7a4d313e
Create Date: 2026-10-20 11:51:51.770372+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd48d67751da3'
down_revision: Union[str, Sequence[str], None] = 'f0ed7a4d313e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('lace_documents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('content_type', sa.String(length=127), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('truncated', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_documents_lace_id_laces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_documents'))
    )
    op.create_index('ix_lace_documents_lace_id_created_at', 'lace_documents', ['lace_id', 'created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_lace_documents_lace_id_created_at', table_name='lace_documents')
    op.drop_table('lace_documents')
