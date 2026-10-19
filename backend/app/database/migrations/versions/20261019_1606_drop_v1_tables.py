"""Drop the v1 tables

workspaces, projects, product_profiles, product_features, competitors,
accounts, chat_messages, outreach_messages, signals and workspace_activity.
Destructive: run only after the pilots are moved into Laces.

Revision ID: 8838b256ea3d
Revises: f0ed7a4d313e
Create Date: 2026-10-19 16:06:44.011060+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8838b256ea3d'
down_revision: Union[str, Sequence[str], None] = 'f0ed7a4d313e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nothing reads these since v1 was retired, and the pilots are in Laces.
    # runs and app_sessions keep their workspace columns for now, unlinked.
    op.drop_constraint(op.f('fk_app_sessions_last_workspace_id_workspaces'), 'app_sessions', type_='foreignkey')
    op.drop_constraint(op.f('fk_runs_workspace_id_workspaces'), 'runs', type_='foreignkey')
    op.drop_index(op.f('ix_product_features_product_profile_id'), table_name='product_features')
    op.drop_table('product_features')
    op.drop_index(op.f('ix_product_profiles_workspace_id'), table_name='product_profiles')
    op.drop_table('product_profiles')
    op.drop_index(op.f('ix_workspace_activity_day'), table_name='workspace_activity')
    op.drop_index(op.f('ix_workspace_activity_user_id'), table_name='workspace_activity')
    op.drop_index(op.f('ix_workspace_activity_workspace_id'), table_name='workspace_activity')
    op.drop_table('workspace_activity')
    op.drop_index(op.f('ix_chat_messages_created_at'), table_name='chat_messages')
    op.drop_index(op.f('ix_chat_messages_run_id'), table_name='chat_messages')
    op.drop_index(op.f('ix_chat_messages_user_id'), table_name='chat_messages')
    op.drop_index(op.f('ix_chat_messages_workspace_id'), table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_index(op.f('ix_outreach_messages_account_id'), table_name='outreach_messages')
    op.drop_index(op.f('ix_outreach_messages_run_id'), table_name='outreach_messages')
    op.drop_index(op.f('ix_outreach_messages_status'), table_name='outreach_messages')
    op.drop_index(op.f('ix_outreach_messages_thread_id'), table_name='outreach_messages')
    op.drop_index(op.f('ix_outreach_messages_user_id'), table_name='outreach_messages')
    op.drop_index(op.f('ix_outreach_messages_workspace_id'), table_name='outreach_messages')
    op.drop_table('outreach_messages')
    op.drop_index(op.f('ix_signals_created_at'), table_name='signals')
    op.drop_index(op.f('ix_signals_run_id'), table_name='signals')
    op.drop_index(op.f('ix_signals_user_id'), table_name='signals')
    op.drop_index(op.f('ix_signals_workspace_id'), table_name='signals')
    op.drop_table('signals')
    op.drop_index(op.f('ix_accounts_review_status'), table_name='accounts')
    op.drop_index(op.f('ix_accounts_run_id'), table_name='accounts')
    op.drop_index(op.f('ix_accounts_via_competitor_id'), table_name='accounts')
    op.drop_index(op.f('ix_accounts_workspace_id'), table_name='accounts')
    op.drop_table('accounts')
    op.drop_index(op.f('ix_competitors_run_id'), table_name='competitors')
    op.drop_index(op.f('ix_competitors_workspace_id'), table_name='competitors')
    op.drop_table('competitors')
    op.drop_index(op.f('ix_workspaces_offer_type'), table_name='workspaces')
    op.drop_index(op.f('ix_workspaces_project_id'), table_name='workspaces')
    op.drop_index(op.f('ix_workspaces_user_id'), table_name='workspaces')
    op.drop_table('workspaces')
    op.drop_index(op.f('ix_projects_user_id'), table_name='projects')
    op.drop_table('projects')



def downgrade() -> None:
    """Downgrade schema."""
    # The tables come back empty: their rows are not restored.
    op.create_table('projects',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('name', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('name_key', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('priority', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
    sa.Column('position', sa.INTEGER(), server_default=sa.text('0'), autoincrement=False, nullable=False),
    sa.Column('archived', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
    sa.Column('archived_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('date_created', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('last_activity', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_projects')),
    sa.UniqueConstraint('user_id', 'name_key', name=op.f('uq_projects_user_name'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_index(op.f('ix_projects_user_id'), 'projects', ['user_id'], unique=False)
    op.create_table('workspaces',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('name', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('pinned', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
    sa.Column('project_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('archived', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
    sa.Column('archived_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('date_created', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('last_activity', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('offer_type', sa.VARCHAR(length=16), autoincrement=False, nullable=True),
    sa.CheckConstraint("offer_type::text = ANY (ARRAY['product'::character varying, 'service'::character varying]::text[])", name=op.f('ck_workspaces_ck_workspaces_offer_type')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_workspaces_project_id_projects'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_workspaces'))
    )
    op.create_index(op.f('ix_workspaces_user_id'), 'workspaces', ['user_id'], unique=False)
    op.create_index(op.f('ix_workspaces_project_id'), 'workspaces', ['project_id'], unique=False)
    op.create_index(op.f('ix_workspaces_offer_type'), 'workspaces', ['offer_type'], unique=False)
    op.create_table('competitors',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('workspace_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('run_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('name', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('website', sa.VARCHAR(length=2048), autoincrement=False, nullable=False),
    sa.Column('domain_key', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('offering', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('positioning', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('business_model', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('pricing', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('target_customers', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('headquarters', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('geography_scope', sa.VARCHAR(length=20), autoincrement=False, nullable=True),
    sa.Column('comparison', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('matched_archetype', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('strengths', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('weaknesses', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('opportunities', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('notable_customers', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('pain_signals', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('customer_sentiment', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('tracking_sources', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('unsourced_fields', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('notes', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('source', sa.VARCHAR(length=20), autoincrement=False, nullable=False),
    sa.Column('first_seen_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('last_seen_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('deep_researched_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('monitor_state', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('last_checked_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('social_profiles', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('socials_checked_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], name=op.f('fk_competitors_run_id_runs'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_competitors_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_competitors')),
    sa.UniqueConstraint('workspace_id', 'domain_key', name=op.f('uq_competitors_workspace_domain'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_index(op.f('ix_competitors_workspace_id'), 'competitors', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_competitors_run_id'), 'competitors', ['run_id'], unique=False)
    op.create_table('accounts',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('workspace_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('run_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('name', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('account_type', sa.VARCHAR(length=20), autoincrement=False, nullable=False),
    sa.Column('website', sa.VARCHAR(length=2048), autoincrement=False, nullable=True),
    sa.Column('domain', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('platform', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('venue', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('event_date', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('member_size', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('industry', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('size', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('geo', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('tech_stack', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('recent_news', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('key_contacts', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('pain_signals', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('hiring_signals', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('sources', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('source_queries', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('score', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    sa.Column('score_breakdown', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('why_selected', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('why_reach_out', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('trigger_event', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('selected', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('summary', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('socials', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), autoincrement=False, nullable=False),
    sa.Column('do_not_contact', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
    sa.Column('fit', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('review_status', sa.VARCHAR(length=16), server_default=sa.text("'target'::character varying"), autoincrement=False, nullable=False),
    sa.Column('via_competitor_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], name=op.f('fk_accounts_run_id_runs'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['via_competitor_id'], ['competitors.id'], name=op.f('fk_accounts_via_competitor_id_competitors'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_accounts_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_accounts')),
    sa.UniqueConstraint('workspace_id', 'name', name=op.f('uq_accounts_workspace_name'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_index(op.f('ix_accounts_workspace_id'), 'accounts', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_accounts_via_competitor_id'), 'accounts', ['via_competitor_id'], unique=False)
    op.create_index(op.f('ix_accounts_run_id'), 'accounts', ['run_id'], unique=False)
    op.create_index(op.f('ix_accounts_review_status'), 'accounts', ['review_status'], unique=False)
    op.create_table('signals',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('workspace_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('run_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('category', sa.VARCHAR(length=20), autoincrement=False, nullable=False),
    sa.Column('title', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('entity', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('summary', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('body', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('reason', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('source_url', sa.VARCHAR(length=2048), autoincrement=False, nullable=True),
    sa.Column('hot', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
    sa.Column('read', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
    sa.Column('pinned', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
    sa.Column('dismissed', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('insight', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], name=op.f('fk_signals_run_id_runs'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_signals_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_signals'))
    )
    op.create_index(op.f('ix_signals_workspace_id'), 'signals', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_signals_user_id'), 'signals', ['user_id'], unique=False)
    op.create_index(op.f('ix_signals_run_id'), 'signals', ['run_id'], unique=False)
    op.create_index(op.f('ix_signals_created_at'), 'signals', ['created_at'], unique=False)
    op.create_table('outreach_messages',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('workspace_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('account_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('run_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('channel', sa.VARCHAR(length=16), autoincrement=False, nullable=False),
    sa.Column('recipient_name', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('recipient_company', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('recipient_address', sa.VARCHAR(length=320), autoincrement=False, nullable=True),
    sa.Column('subject', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('body', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('status', sa.VARCHAR(length=16), autoincrement=False, nullable=False),
    sa.Column('error', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('provider_log_id', sa.VARCHAR(length=64), autoincrement=False, nullable=True),
    sa.Column('sent_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('direction', sa.VARCHAR(length=8), server_default=sa.text("'outbound'::character varying"), autoincrement=False, nullable=False),
    sa.Column('thread_id', sa.VARCHAR(length=64), autoincrement=False, nullable=True),
    sa.Column('provider_message_id', sa.VARCHAR(length=128), autoincrement=False, nullable=True),
    sa.Column('read_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('intent', sa.VARCHAR(length=24), autoincrement=False, nullable=True),
    sa.Column('meeting', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.CheckConstraint("direction::text = ANY (ARRAY['outbound'::character varying, 'inbound'::character varying]::text[])", name=op.f('ck_outreach_messages_ck_outreach_messages_direction')),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], name=op.f('fk_outreach_messages_account_id_accounts'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], name=op.f('fk_outreach_messages_run_id_runs'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_outreach_messages_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_outreach_messages')),
    sa.UniqueConstraint('user_id', 'provider_message_id', name=op.f('uq_outreach_messages_user_provider_message'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_index(op.f('ix_outreach_messages_workspace_id'), 'outreach_messages', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_outreach_messages_user_id'), 'outreach_messages', ['user_id'], unique=False)
    op.create_index(op.f('ix_outreach_messages_thread_id'), 'outreach_messages', ['thread_id'], unique=False)
    op.create_index(op.f('ix_outreach_messages_status'), 'outreach_messages', ['status'], unique=False)
    op.create_index(op.f('ix_outreach_messages_run_id'), 'outreach_messages', ['run_id'], unique=False)
    op.create_index(op.f('ix_outreach_messages_account_id'), 'outreach_messages', ['account_id'], unique=False)
    op.create_table('chat_messages',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('workspace_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('role', sa.VARCHAR(length=16), autoincrement=False, nullable=False),
    sa.Column('content', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('run_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('specialist_domain', sa.VARCHAR(length=16), autoincrement=False, nullable=True),
    sa.Column('suggestions', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], name=op.f('fk_chat_messages_run_id_runs'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_chat_messages_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_chat_messages'))
    )
    op.create_index(op.f('ix_chat_messages_workspace_id'), 'chat_messages', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_chat_messages_user_id'), 'chat_messages', ['user_id'], unique=False)
    op.create_index(op.f('ix_chat_messages_run_id'), 'chat_messages', ['run_id'], unique=False)
    op.create_index(op.f('ix_chat_messages_created_at'), 'chat_messages', ['created_at'], unique=False)
    op.create_table('workspace_activity',
    sa.Column('id', sa.BIGINT(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('workspace_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('day', sa.DATE(), autoincrement=False, nullable=False),
    sa.Column('active_seconds', sa.INTEGER(), server_default=sa.text('0'), autoincrement=False, nullable=False),
    sa.Column('visits', sa.INTEGER(), server_default=sa.text('0'), autoincrement=False, nullable=False),
    sa.Column('last_seen_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_workspace_activity_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_workspace_activity')),
    sa.UniqueConstraint('workspace_id', 'day', name=op.f('uq_workspace_activity_workspace_day'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_index(op.f('ix_workspace_activity_workspace_id'), 'workspace_activity', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_workspace_activity_user_id'), 'workspace_activity', ['user_id'], unique=False)
    op.create_index(op.f('ix_workspace_activity_day'), 'workspace_activity', ['day'], unique=False)
    op.create_table('product_profiles',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('workspace_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('product_name', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('product_url', sa.VARCHAR(length=2048), autoincrement=False, nullable=True),
    sa.Column('product_description', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('intent', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('problem_solved', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('how_it_works', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('target_geo', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('confirmed', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
    sa.Column('insights', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_product_profiles_workspace_id_workspaces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_product_profiles'))
    )
    op.create_index(op.f('ix_product_profiles_workspace_id'), 'product_profiles', ['workspace_id'], unique=True)
    op.create_table('product_features',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('product_profile_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('name', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('differentiator', sa.TEXT(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['product_profile_id'], ['product_profiles.id'], name=op.f('fk_product_features_product_profile_id_product_profiles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_product_features'))
    )
    op.create_index(op.f('ix_product_features_product_profile_id'), 'product_features', ['product_profile_id'], unique=False)
    # The workspaces they pointed at are gone, so the links can't come back.
    op.execute("UPDATE runs SET workspace_id = NULL WHERE workspace_id IS NOT NULL")
    op.execute("UPDATE app_sessions SET last_workspace_id = NULL WHERE last_workspace_id IS NOT NULL")
    op.create_foreign_key(op.f('fk_runs_workspace_id_workspaces'), 'runs', 'workspaces', ['workspace_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(op.f('fk_app_sessions_last_workspace_id_workspaces'), 'app_sessions', 'workspaces', ['last_workspace_id'], ['id'], ondelete='SET NULL')

