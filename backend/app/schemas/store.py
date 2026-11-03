"""A Lace's Store as the team sets it up: the Store, its offers and the
revenue split. The grant token never leaves the backend, so no shape here
carries it."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, field_serializer, model_validator

from agents.schemas.store import (FULL_SHARE_BPS, STORE_SLUG_PATTERN, OfferDelivery, OfferStatus, PayeeRoute,
                                  StoreStatus)
from backend.app.services.store import MAX_PAYEES

Slug = Annotated[str, StringConstraints(pattern=STORE_SLUG_PATTERN)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
# A day's cap the founder signs: at least a dollar, at most what a small Store needs.
Budget = Annotated[Decimal, Field(ge=1, le=100_000, decimal_places=2)]


class StoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    tagline: str
    status: StoreStatus
    shown: bool
    settlement_asset: str
    daily_budget_usd: Decimal
    owner_account_id: str | None
    # Where sales land: the Store's own NEAR Intents account, once it exists.
    wallet_account_id: str | None
    frozen_at: datetime | None
    live_since: datetime | None

    @field_serializer("daily_budget_usd")
    def _budget(self, value: Decimal) -> str:
        return f"{value:.2f}"


class StoreShownRequest(BaseModel):
    shown: bool


class StoreUpdate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None
    tagline: Annotated[str, StringConstraints(max_length=280)] | None = None
    slug: Slug | None = None
    daily_budget_usd: Budget | None = None


class OfferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str
    price_cents: int
    delivery: OfferDelivery
    delivery_url: str | None
    delivery_note: str
    status: OfferStatus
    drafted_by_lace: bool
    created_at: datetime


class OfferCreate(BaseModel):
    title: Title
    description: Annotated[str, StringConstraints(max_length=4000)] = ""
    # Whole cents, at least a dollar: below that, network minimums eat the sale.
    price_cents: int = Field(ge=100, le=10_000_000)
    delivery: OfferDelivery
    delivery_url: HttpUrl | None = None
    delivery_note: Annotated[str, StringConstraints(max_length=2000)] = ""
    status: OfferStatus = "draft"


class OfferUpdate(BaseModel):
    title: Title | None = None
    description: Annotated[str, StringConstraints(max_length=4000)] | None = None
    price_cents: int | None = Field(default=None, ge=100, le=10_000_000)
    delivery: OfferDelivery | None = None
    delivery_url: HttpUrl | None = None
    delivery_note: Annotated[str, StringConstraints(max_length=2000)] | None = None
    status: OfferStatus | None = None


class PayeeIn(BaseModel):
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    route: PayeeRoute
    # Withdrawals only: the chain id as NEAR Intents lists it (near, base, eth, sol...).
    chain: Annotated[str, StringConstraints(pattern=r"^[a-z0-9]{2,24}$")] | None = None
    address: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=128)]
    memo: Annotated[str, StringConstraints(max_length=128)] | None = None
    share_bps: int = Field(gt=0, le=FULL_SHARE_BPS)

    @model_validator(mode="after")
    def _chain_for_withdrawals(self) -> "PayeeIn":
        if (self.route == "withdraw") != (self.chain is not None):
            raise ValueError("A withdrawal names its chain; a transfer to a NEAR Intents account doesn't.")
        return self


class PayeesUpdate(BaseModel):
    payees: list[PayeeIn] = Field(max_length=MAX_PAYEES)


class PayeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    route: PayeeRoute
    chain: str | None
    address: str
    memo: str | None
    share_bps: int
