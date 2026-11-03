"""Tables for a Lace's Store: its offers, who shares in each sale, the orders
buyers place, the public ledger, and the owner signatures it waits on.

The money itself is in the Store's NEAR Intents Agent API wallet. These rows
are our record of it: every amount that moved has a correlation id there."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UUID,
                        UniqueConstraint, false, func, text)
from sqlalchemy.orm import Mapped, mapped_column

from agents.schemas.store import (FULL_SHARE_BPS, LEDGER_KINDS, LEDGER_STATUSES, OFFER_DELIVERIES, OFFER_STATUSES,
                                  ORDER_STATUSES, PAYEE_ROUTES, STORE_INTENT_STATUSES, STORE_INTENT_TYPES,
                                  STORE_SLUG_MAX_LEN, STORE_SLUG_PATTERN, STORE_STATUSES)
from backend.app.database.connect import Base

# NEAR Intents amounts are atomic units of up to 128 bits.
ATOMIC = Numeric(40, 0)
# Asset ids such as "nep141:base-0x8335...02913.omft.near".
ASSET_ID_LEN = 128
# Agent API ids: a 64-hex agent id, "op_…"/"intent_…" correlation ids.
API_ID_LEN = 96
# NEAR account ids are at most 64 characters; chain addresses fit in 128.
ADDRESS_LEN = 128


def _one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _now() -> datetime:
    return datetime.now(UTC)


class LaceStore(Base):
    """A Lace's Store, one per Lace. Made the first time the team turns the
    Store on, and kept when they hide it again."""

    __tablename__ = "lace_stores"
    __table_args__ = (
        CheckConstraint(_one_of("status", STORE_STATUSES), name="status"),
        CheckConstraint(f"slug ~ '{STORE_SLUG_PATTERN}'", name="slug_format"),
        CheckConstraint("status = 'setup' OR agent_id IS NOT NULL", name="live_has_agent"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("laces.id", ondelete="CASCADE"), nullable=False,
                                               unique=True)
    # The public address: /s/<slug>.
    slug: Mapped[str] = mapped_column(String(STORE_SLUG_MAX_LEN), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    tagline: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="setup", server_default="setup")
    # Whether the Store's tab shows on the Lace's rail.
    shown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    # What every sale is credited as, whatever the buyer pays with.
    settlement_asset: Mapped[str] = mapped_column(String(ASSET_ID_LEN), nullable=False)
    # The founder's own USD cap on what the Store may send out in a day. The
    # signed policy enforces it; this is the value the team last signed.
    daily_budget_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Who signs for the Store: the founder's passkey (public data only), set in
    # setup and fixed once the agent exists. The public key is P-256 SPKI,
    # base64url. The NEAR account the API derives from it is owner_account_id.
    owner_account_id: Mapped[str | None] = mapped_column(String(ADDRESS_LEN), nullable=True)
    owner_public_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    owner_credential_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    owner_rp_id: Mapped[str | None] = mapped_column(String(253), nullable=True)
    owner_origin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # The Agent API agent and its NEAR Intents account, where sales land.
    agent_id: Mapped[str | None] = mapped_column(String(API_ID_LEN), nullable=True, unique=True)
    wallet_account_id: Mapped[str | None] = mapped_column(String(ADDRESS_LEN), nullable=True)
    policy_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The grant our backend acts under, its token encrypted (never shown).
    grant_id: Mapped[str | None] = mapped_column(String(API_ID_LEN), nullable=True)
    grant_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    grant_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set while the founder's wallet freeze is on: nothing can move money.
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    live_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now,
                                                 server_default=func.now(), onupdate=_now)


class StoreOffer(Base):
    """Something the Store sells, at a fixed USD price."""

    __tablename__ = "store_offers"
    __table_args__ = (
        CheckConstraint(_one_of("delivery", OFFER_DELIVERIES), name="delivery"),
        CheckConstraint(_one_of("status", OFFER_STATUSES), name="status"),
        CheckConstraint("price_cents > 0", name="price_positive"),
        CheckConstraint("delivery <> 'link' OR delivery_url IS NOT NULL", name="link_has_url"),
        Index("ix_store_offers_store_id_status_position", "store_id", "status", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Indexed by the status index, which leads with it.
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lace_stores.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery: Mapped[str] = mapped_column(String(12), nullable=False)
    # Private: emailed to the buyer once paid, never shown on the storefront.
    delivery_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # What the buyer's email says alongside it, or what the team will do.
    delivery_note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="draft", server_default="draft")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Drafted by the Lace in chat: a person puts it on sale.
    drafted_by_lace: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    # Supabase owns users: no FK. None for the Lace's drafts.
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now,
                                                 server_default=func.now(), onupdate=_now)


class StorePayee(Base):
    """One share of every sale and where it goes: the revenue split. Each
    payee's address is a destination in the signed policy, so the wallet
    refuses to pay anywhere else."""

    __tablename__ = "store_payees"
    __table_args__ = (
        CheckConstraint(_one_of("route", PAYEE_ROUTES), name="route"),
        CheckConstraint(f"share_bps > 0 AND share_bps <= {FULL_SHARE_BPS}", name="share_range"),
        CheckConstraint("(route = 'withdraw') = (chain IS NOT NULL)", name="withdraw_has_chain"),
        UniqueConstraint("store_id", "route", "chain", "address", name="uq_store_payees_destination",
                         postgresql_nulls_not_distinct=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Indexed by the unique constraint, which leads with it.
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lace_stores.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    route: Mapped[str] = mapped_column(String(10), nullable=False)
    chain: Mapped[str | None] = mapped_column(String(24), nullable=True)
    address: Mapped[str] = mapped_column(String(ADDRESS_LEN), nullable=False)
    memo: Mapped[str | None] = mapped_column(String(128), nullable=True)
    share_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=_now, server_default=func.now())


class StoreOrder(Base):
    """One purchase: the one-time deposit address the buyer pays into, then
    what arrived, and the delivery."""

    __tablename__ = "store_orders"
    __table_args__ = (
        CheckConstraint(_one_of("status", ORDER_STATUSES), name="status"),
        Index("ix_store_orders_store_id_created_at", "store_id", "created_at"),
        Index("ix_store_orders_open", "status", "created_at",
              postgresql_where=text("status IN ('awaiting_payment', 'paid')")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Indexed by the created_at index, which leads with it.
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lace_stores.id", ondelete="CASCADE"), nullable=False)
    # Offers are archived, never deleted, once anyone bought one.
    offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store_offers.id", ondelete="RESTRICT"),
                                                nullable=False, index=True)
    # The buyer's own handle on the order (its status page), not guessable.
    public_token: Mapped[str] = mapped_column(String(48), nullable=False, unique=True)
    buyer_email: Mapped[str] = mapped_column(String(320), nullable=False)
    # The price when ordered, whatever the offer says later.
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    pay_asset: Mapped[str] = mapped_column(String(ASSET_ID_LEN), nullable=False)
    # Exactly what the buyer was asked to send, in pay_asset's atomic units.
    pay_amount_raw: Mapped[Decimal] = mapped_column(ATOMIC, nullable=False)
    deposit_idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    deposit_correlation_id: Mapped[str | None] = mapped_column(String(API_ID_LEN), nullable=True, unique=True)
    deposit_address: Mapped[str | None] = mapped_column(String(ADDRESS_LEN), nullable=True)
    deposit_memo: Mapped[str | None] = mapped_column(String(128), nullable=True)
    deposit_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="awaiting_payment",
                                        server_default="awaiting_payment")
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # What the wallet was credited, in the Store's settlement asset.
    credited_raw: Mapped[Decimal | None] = mapped_column(ATOMIC, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When the watcher last asked the Agent API about the deposit.
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=_now, server_default=func.now())


class StoreLedgerEntry(Base):
    """One line of the Store's public ledger. Rows are added, and a pending
    one settles; nothing is rewritten. A payout's idempotency key is made
    and saved before it is sent, so a retry never pays twice."""

    __tablename__ = "store_ledger"
    __table_args__ = (
        CheckConstraint(_one_of("kind", LEDGER_KINDS), name="kind"),
        CheckConstraint(_one_of("status", LEDGER_STATUSES), name="status"),
        CheckConstraint("kind <> 'payout' OR (payee_id IS NOT NULL AND order_id IS NOT NULL)",
                        name="payout_has_payee"),
        UniqueConstraint("order_id", "kind", "payee_id", name="uq_store_ledger_order_id_kind_payee_id",
                         postgresql_nulls_not_distinct=True),
        Index("ix_store_ledger_store_id_created_at", "store_id", "created_at"),
        Index("ix_store_ledger_pending", "status", postgresql_where=text("status = 'pending'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Indexed by the created_at index, which leads with it.
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lace_stores.id", ondelete="CASCADE"), nullable=False)
    # Indexed by the unique constraint, which leads with it.
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("store_orders.id", ondelete="CASCADE"),
                                                       nullable=True)
    payee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("store_payees.id", ondelete="SET NULL"),
                                                       nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="pending", server_default="pending")
    asset: Mapped[str] = mapped_column(String(ASSET_ID_LEN), nullable=False)
    amount_raw: Mapped[Decimal] = mapped_column(ATOMIC, nullable=False)
    # Its USD value when recorded, for totals; None when no price was known.
    amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    # Who it went to or came from, as the ledger shows it.
    counterparty: Mapped[str | None] = mapped_column(String(ADDRESS_LEN), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    correlation_id: Mapped[str | None] = mapped_column(String(API_ID_LEN), nullable=True, unique=True)
    tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=_now, server_default=func.now())
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StoreIntent(Base):
    """An owner signature the Store is waiting on, generated for one person
    on the team. Only they may submit it; the API's correlation id is not
    trusted from a browser on its own."""

    __tablename__ = "store_intents"
    __table_args__ = (
        CheckConstraint(_one_of("type", STORE_INTENT_TYPES), name="type"),
        CheckConstraint(_one_of("status", STORE_INTENT_STATUSES), name="status"),
        Index("ix_store_intents_store_id_created_at", "store_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Indexed by the created_at index, which leads with it.
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lace_stores.id", ondelete="CASCADE"), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(API_ID_LEN), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="awaiting_signature",
                                        server_default="awaiting_signature")
    # Supabase owns users: no FK. Indexed for "what's waiting on me".
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # A grant_issue's token, encrypted, until the grant is live on the Store.
    grant_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=_now, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
