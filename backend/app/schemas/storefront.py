"""A Store as the public sees it: its storefront, and an order's page. No
delivery link, payee or wallet detail is ever part of these."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, StringConstraints
from typing import Annotated

from agents.schemas.store import OfferDelivery, OrderStatus


class PublicOffer(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    price_cents: int
    delivery: OfferDelivery


class PayCoin(BaseModel):
    asset_id: str
    symbol: str
    # The chain the buyer sends from, as NEAR Intents names it (near, base, arb...).
    chain: str


class StorefrontResponse(BaseModel):
    slug: str
    name: str
    tagline: str
    # False while the team paused it or its wallet is frozen: offers show, checkout doesn't.
    selling: bool
    offers: list[PublicOffer]
    pay_with: list[PayCoin]


class OrderCreate(BaseModel):
    offer_id: uuid.UUID
    email: EmailStr
    pay_asset: Annotated[str, StringConstraints(max_length=128)]


class OrderResponse(BaseModel):
    """What the buyer's order page shows. `token` is its only key."""
    token: str
    status: OrderStatus
    store_name: str
    store_slug: str
    offer_title: str
    price_cents: int
    pay_coin: PayCoin | None
    # Exactly what to send, as a decimal string in the coin's own units.
    pay_amount: str
    deposit_address: str | None
    deposit_memo: str | None
    deposit_expires_at: datetime | None
    paid_at: datetime | None
    delivered_at: datetime | None
    created_at: datetime
