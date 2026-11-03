"""add_lace_stores

A Lace's Store (NEAR HACKATHON): its offers, revenue-split payees, orders,
public ledger and the owner signatures it waits on, plus Feed items for a
sale, a payout and the Store going live, pausing or freezing.

Revision ID: 24286ff21378
Revises: 5e2a9c7d1b43
Create Date: 2026-11-03 14:18:29.221621+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

_KINDS = ("'brief', 'competitors_found', 'competitor_moves', 'accounts_found', 'contacts_found', "
          "'drafts_ready', 'reply_received', 'opportunities_found', 'job_failed', 'app_action', 'access_requested', "
          "'comments_read', 'member_joined', 'message_sent', 'competitor_saved', 'account_saved', "
          "'opportunity_saved', 'finds_proposed', 'finds_returned', 'regulations_found', 'bill_moved'")
_STORE_KINDS = "'store_sale', 'store_payout', 'store_status'"
_REFS = "'brief', 'outreach', 'app_action'"


def _activity(kinds: str, refs: str) -> None:
    op.drop_constraint(op.f("ck_lace_activity_kind"), "lace_activity", type_="check")
    op.create_check_constraint(op.f("ck_lace_activity_kind"), "lace_activity", f"kind IN ({kinds})")
    op.drop_constraint(op.f("ck_lace_activity_ref_type"), "lace_activity", type_="check")
    op.create_check_constraint(op.f("ck_lace_activity_ref_type"), "lace_activity",
                               f"ref_type IS NULL OR ref_type IN ({refs})")


# revision identifiers, used by Alembic.
revision: str = '24286ff21378'
down_revision: Union[str, Sequence[str], None] = '5e2a9c7d1b43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('lace_stores',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('lace_id', sa.UUID(), nullable=False),
    sa.Column('slug', sa.String(length=48), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('tagline', sa.Text(), server_default='', nullable=False),
    sa.Column('status', sa.String(length=12), server_default='setup', nullable=False),
    sa.Column('shown', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('settlement_asset', sa.String(length=128), nullable=False),
    sa.Column('daily_budget_usd', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('owner_account_id', sa.String(length=128), nullable=True),
    sa.Column('owner_public_key', sa.String(length=128), nullable=True),
    sa.Column('agent_id', sa.String(length=96), nullable=True),
    sa.Column('wallet_account_id', sa.String(length=128), nullable=True),
    sa.Column('policy_revision', sa.Integer(), nullable=True),
    sa.Column('grant_id', sa.String(length=96), nullable=True),
    sa.Column('grant_token_enc', sa.Text(), nullable=True),
    sa.Column('grant_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('frozen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('live_since', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("slug ~ '^[a-z0-9](?:[a-z0-9-]{1,46}[a-z0-9])$'", name=op.f('ck_lace_stores_slug_format')),
    sa.CheckConstraint("status = 'setup' OR agent_id IS NOT NULL", name=op.f('ck_lace_stores_live_has_agent')),
    sa.CheckConstraint("status IN ('setup', 'live', 'paused')", name=op.f('ck_lace_stores_status')),
    sa.ForeignKeyConstraint(['lace_id'], ['laces.id'], name=op.f('fk_lace_stores_lace_id_laces'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lace_stores')),
    sa.UniqueConstraint('agent_id', name=op.f('uq_lace_stores_agent_id')),
    sa.UniqueConstraint('lace_id', name=op.f('uq_lace_stores_lace_id')),
    sa.UniqueConstraint('slug', name=op.f('uq_lace_stores_slug'))
    )
    op.create_table('store_intents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('store_id', sa.UUID(), nullable=False),
    sa.Column('correlation_id', sa.String(length=96), nullable=False),
    sa.Column('type', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='awaiting_signature', nullable=False),
    sa.Column('requested_by', sa.UUID(), nullable=False),
    sa.Column('grant_token_enc', sa.Text(), nullable=True),
    sa.Column('failure_code', sa.String(length=64), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('awaiting_signature', 'submitted', 'succeeded', 'failed', 'expired')", name=op.f('ck_store_intents_status')),
    sa.CheckConstraint("type IN ('agent_create', 'grant_issue', 'policy_update', 'agent_freeze', 'agent_unfreeze')", name=op.f('ck_store_intents_type')),
    sa.ForeignKeyConstraint(['store_id'], ['lace_stores.id'], name=op.f('fk_store_intents_store_id_lace_stores'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_store_intents')),
    sa.UniqueConstraint('correlation_id', name=op.f('uq_store_intents_correlation_id'))
    )
    op.create_index(op.f('ix_store_intents_requested_by'), 'store_intents', ['requested_by'], unique=False)
    op.create_index('ix_store_intents_store_id_created_at', 'store_intents', ['store_id', 'created_at'], unique=False)
    op.create_table('store_offers',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('store_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('description', sa.Text(), server_default='', nullable=False),
    sa.Column('price_cents', sa.Integer(), nullable=False),
    sa.Column('delivery', sa.String(length=12), nullable=False),
    sa.Column('delivery_url', sa.Text(), nullable=True),
    sa.Column('delivery_note', sa.Text(), server_default='', nullable=False),
    sa.Column('status', sa.String(length=12), server_default='draft', nullable=False),
    sa.Column('position', sa.Integer(), server_default='0', nullable=False),
    sa.Column('drafted_by_lace', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("delivery <> 'link' OR delivery_url IS NOT NULL", name=op.f('ck_store_offers_link_has_url')),
    sa.CheckConstraint("delivery IN ('link', 'service')", name=op.f('ck_store_offers_delivery')),
    sa.CheckConstraint("status IN ('draft', 'active', 'archived')", name=op.f('ck_store_offers_status')),
    sa.CheckConstraint('price_cents > 0', name=op.f('ck_store_offers_price_positive')),
    sa.ForeignKeyConstraint(['store_id'], ['lace_stores.id'], name=op.f('fk_store_offers_store_id_lace_stores'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_store_offers'))
    )
    op.create_index('ix_store_offers_store_id_status_position', 'store_offers', ['store_id', 'status', 'position'], unique=False)
    op.create_table('store_payees',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('store_id', sa.UUID(), nullable=False),
    sa.Column('label', sa.String(length=80), nullable=False),
    sa.Column('route', sa.String(length=10), nullable=False),
    sa.Column('chain', sa.String(length=24), nullable=True),
    sa.Column('address', sa.String(length=128), nullable=False),
    sa.Column('memo', sa.String(length=128), nullable=True),
    sa.Column('share_bps', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(route = 'withdraw') = (chain IS NOT NULL)", name=op.f('ck_store_payees_withdraw_has_chain')),
    sa.CheckConstraint("route IN ('transfer', 'withdraw')", name=op.f('ck_store_payees_route')),
    sa.CheckConstraint('share_bps > 0 AND share_bps <= 10000', name=op.f('ck_store_payees_share_range')),
    sa.ForeignKeyConstraint(['store_id'], ['lace_stores.id'], name=op.f('fk_store_payees_store_id_lace_stores'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_store_payees')),
    sa.UniqueConstraint('store_id', 'route', 'chain', 'address', name='uq_store_payees_destination', postgresql_nulls_not_distinct=True)
    )
    op.create_table('store_orders',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('store_id', sa.UUID(), nullable=False),
    sa.Column('offer_id', sa.UUID(), nullable=False),
    sa.Column('public_token', sa.String(length=48), nullable=False),
    sa.Column('buyer_email', sa.String(length=320), nullable=False),
    sa.Column('price_cents', sa.Integer(), nullable=False),
    sa.Column('pay_asset', sa.String(length=128), nullable=False),
    sa.Column('pay_amount_raw', sa.Numeric(precision=40, scale=0), nullable=False),
    sa.Column('deposit_idempotency_key', sa.String(length=128), nullable=False),
    sa.Column('deposit_correlation_id', sa.String(length=96), nullable=True),
    sa.Column('deposit_address', sa.String(length=128), nullable=True),
    sa.Column('deposit_memo', sa.String(length=128), nullable=True),
    sa.Column('deposit_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=16), server_default='awaiting_payment', nullable=False),
    sa.Column('failure_code', sa.String(length=64), nullable=True),
    sa.Column('credited_raw', sa.Numeric(precision=40, scale=0), nullable=True),
    sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('awaiting_payment', 'paid', 'delivered', 'refunded', 'failed', 'expired')", name=op.f('ck_store_orders_status')),
    sa.ForeignKeyConstraint(['offer_id'], ['store_offers.id'], name=op.f('fk_store_orders_offer_id_store_offers'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['store_id'], ['lace_stores.id'], name=op.f('fk_store_orders_store_id_lace_stores'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_store_orders')),
    sa.UniqueConstraint('deposit_correlation_id', name=op.f('uq_store_orders_deposit_correlation_id')),
    sa.UniqueConstraint('deposit_idempotency_key', name=op.f('uq_store_orders_deposit_idempotency_key')),
    sa.UniqueConstraint('public_token', name=op.f('uq_store_orders_public_token'))
    )
    op.create_index(op.f('ix_store_orders_offer_id'), 'store_orders', ['offer_id'], unique=False)
    op.create_index('ix_store_orders_open', 'store_orders', ['status', 'created_at'], unique=False, postgresql_where=sa.text("status IN ('awaiting_payment', 'paid')"))
    op.create_index('ix_store_orders_store_id_created_at', 'store_orders', ['store_id', 'created_at'], unique=False)
    op.create_table('store_ledger',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('store_id', sa.UUID(), nullable=False),
    sa.Column('order_id', sa.UUID(), nullable=True),
    sa.Column('payee_id', sa.UUID(), nullable=True),
    sa.Column('kind', sa.String(length=8), nullable=False),
    sa.Column('status', sa.String(length=8), server_default='pending', nullable=False),
    sa.Column('asset', sa.String(length=128), nullable=False),
    sa.Column('amount_raw', sa.Numeric(precision=40, scale=0), nullable=False),
    sa.Column('amount_usd', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('counterparty', sa.String(length=128), nullable=True),
    sa.Column('idempotency_key', sa.String(length=128), nullable=True),
    sa.Column('correlation_id', sa.String(length=96), nullable=True),
    sa.Column('tx_hash', sa.String(length=128), nullable=True),
    sa.Column('failure_code', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("kind <> 'payout' OR (payee_id IS NOT NULL AND order_id IS NOT NULL)", name=op.f('ck_store_ledger_payout_has_payee')),
    sa.CheckConstraint("kind IN ('sale', 'payout', 'refund', 'cost')", name=op.f('ck_store_ledger_kind')),
    sa.CheckConstraint("status IN ('pending', 'done', 'failed')", name=op.f('ck_store_ledger_status')),
    sa.ForeignKeyConstraint(['order_id'], ['store_orders.id'], name=op.f('fk_store_ledger_order_id_store_orders'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['payee_id'], ['store_payees.id'], name=op.f('fk_store_ledger_payee_id_store_payees'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['store_id'], ['lace_stores.id'], name=op.f('fk_store_ledger_store_id_lace_stores'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_store_ledger')),
    sa.UniqueConstraint('correlation_id', name=op.f('uq_store_ledger_correlation_id')),
    sa.UniqueConstraint('idempotency_key', name=op.f('uq_store_ledger_idempotency_key')),
    sa.UniqueConstraint('order_id', 'kind', 'payee_id', name='uq_store_ledger_order_id_kind_payee_id', postgresql_nulls_not_distinct=True)
    )
    op.create_index(op.f('ix_store_ledger_payee_id'), 'store_ledger', ['payee_id'], unique=False)
    op.create_index('ix_store_ledger_pending', 'store_ledger', ['status'], unique=False, postgresql_where=sa.text("status = 'pending'"))
    op.create_index('ix_store_ledger_store_id_created_at', 'store_ledger', ['store_id', 'created_at'], unique=False)
    _activity(f"{_KINDS}, {_STORE_KINDS}", f"{_REFS}, 'store_order'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(f"DELETE FROM lace_activity WHERE kind IN ({_STORE_KINDS}) OR ref_type = 'store_order'")
    _activity(_KINDS, _REFS)
    op.drop_index('ix_store_ledger_store_id_created_at', table_name='store_ledger')
    op.drop_index('ix_store_ledger_pending', table_name='store_ledger', postgresql_where=sa.text("status = 'pending'"))
    op.drop_index(op.f('ix_store_ledger_payee_id'), table_name='store_ledger')
    op.drop_table('store_ledger')
    op.drop_index('ix_store_orders_store_id_created_at', table_name='store_orders')
    op.drop_index('ix_store_orders_open', table_name='store_orders', postgresql_where=sa.text("status IN ('awaiting_payment', 'paid')"))
    op.drop_index(op.f('ix_store_orders_offer_id'), table_name='store_orders')
    op.drop_table('store_orders')
    op.drop_table('store_payees')
    op.drop_index('ix_store_offers_store_id_status_position', table_name='store_offers')
    op.drop_table('store_offers')
    op.drop_index('ix_store_intents_store_id_created_at', table_name='store_intents')
    op.drop_index(op.f('ix_store_intents_requested_by'), table_name='store_intents')
    op.drop_table('store_intents')
    op.drop_table('lace_stores')
