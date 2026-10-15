"""add waitlist_signups

People who join the waitlist on the public landing page (gtmx.co), with the
optional details they add and whether they want the pilot. Not Supabase users,
so no user FK; email is the natural key.

Revision ID: 6a1c3e5b7d92
Revises: 4e8a2c6b1d97
Create Date: 2026-10-13 09:00:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '6a1c3e5b7d92'
down_revision: Union[str, Sequence[str], None] = '4e8a2c6b1d97'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'waitlist_signups',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=True),
        sa.Column('company', sa.String(length=200), nullable=True),
        sa.Column('role', sa.String(length=120), nullable=True),
        sa.Column('stage', sa.String(length=16), nullable=True),
        sa.Column('sells_to', sa.String(length=8), nullable=True),
        sa.Column('countries', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('wants_pilot', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('expectations', sa.Text(), nullable=True),
        sa.Column('source', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('status', sa.String(length=16), server_default='new', nullable=False),
        sa.Column('update_token_hash', sa.String(length=64), nullable=False),
        sa.Column('ip_hash', sa.String(length=64), nullable=True),
        sa.Column('consent_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('confirmation_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("stage IS NULL OR stage IN ('idea', 'pre_revenue', 'revenue', 'scaling')",
                           name='ck_waitlist_signups_stage'),
        sa.CheckConstraint("sells_to IS NULL OR sells_to IN ('b2b', 'b2c', 'both')", name='ck_waitlist_signups_sells_to'),
        sa.CheckConstraint("status IN ('new', 'contacted', 'invited', 'onboarded')", name='ck_waitlist_signups_status'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('update_token_hash'),
    )
    op.create_index(op.f('ix_waitlist_signups_wants_pilot'), 'waitlist_signups', ['wants_pilot'], unique=False)
    op.create_index(op.f('ix_waitlist_signups_status'), 'waitlist_signups', ['status'], unique=False)
    op.create_index(op.f('ix_waitlist_signups_ip_hash'), 'waitlist_signups', ['ip_hash'], unique=False)
    op.create_index(op.f('ix_waitlist_signups_created_at'), 'waitlist_signups', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_waitlist_signups_created_at'), table_name='waitlist_signups')
    op.drop_index(op.f('ix_waitlist_signups_ip_hash'), table_name='waitlist_signups')
    op.drop_index(op.f('ix_waitlist_signups_status'), table_name='waitlist_signups')
    op.drop_index(op.f('ix_waitlist_signups_wants_pilot'), table_name='waitlist_signups')
    op.drop_table('waitlist_signups')
