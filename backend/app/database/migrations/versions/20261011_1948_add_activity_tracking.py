"""add activity tracking

app_sessions (active time per stretch of use) and workspace_activity
(active time and visits per workspace per day), fed by customer-app
heartbeats. New tables only.

Revision ID: 201d9b8547dd
Revises: 2b7c1e9d4f30
Create Date: 2026-10-11 19:48:35.314624+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '201d9b8547dd'
down_revision: Union[str, Sequence[str], None] = '2b7c1e9d4f30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('app_sessions',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('active_seconds', sa.Integer(), server_default='0', nullable=False),
    sa.Column('last_workspace_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['last_workspace_id'], ['workspaces.id'], name=op.f('fk_app_sessions_last_workspace_id_workspaces'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_app_sessions'))
    )
    op.create_index(op.f('ix_app_sessions_last_seen_at'), 'app_sessions', ['last_seen_at'], unique=False)
    op.create_index(op.f('ix_app_sessions_last_workspace_id'), 'app_sessions', ['last_workspace_id'], unique=False)
    op.create_index(op.f('ix_app_sessions_started_at'), 'app_sessions', ['started_at'], unique=False)
    op.create_index(op.f('ix_app_sessions_user_id'), 'app_sessions', ['user_id'], unique=False)
    op.create_table('workspace_activity',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('workspace_id', sa.UUID(), nullable=False),
    sa.Column('day', sa.Date(), nullable=False),
    sa.Column('active_seconds', sa.Integer(), server_default='0', nullable=False),
    sa.Column('visits', sa.Integer(), server_default='0', nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_workspace_activity_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_workspace_activity')),
    sa.UniqueConstraint('workspace_id', 'day', name='uq_workspace_activity_workspace_day')
    )
    op.create_index(op.f('ix_workspace_activity_day'), 'workspace_activity', ['day'], unique=False)
    op.create_index(op.f('ix_workspace_activity_user_id'), 'workspace_activity', ['user_id'], unique=False)
    op.create_index(op.f('ix_workspace_activity_workspace_id'), 'workspace_activity', ['workspace_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_workspace_activity_workspace_id'), table_name='workspace_activity')
    op.drop_index(op.f('ix_workspace_activity_user_id'), table_name='workspace_activity')
    op.drop_index(op.f('ix_workspace_activity_day'), table_name='workspace_activity')
    op.drop_table('workspace_activity')
    op.drop_index(op.f('ix_app_sessions_user_id'), table_name='app_sessions')
    op.drop_index(op.f('ix_app_sessions_started_at'), table_name='app_sessions')
    op.drop_index(op.f('ix_app_sessions_last_workspace_id'), table_name='app_sessions')
    op.drop_index(op.f('ix_app_sessions_last_seen_at'), table_name='app_sessions')
    op.drop_table('app_sessions')
