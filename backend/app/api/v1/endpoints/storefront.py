"""A Store's public pages: no sign-in. Anyone can see a live Store and buy
from it; an order's page is reached only by the token its buyer was given.
Checkouts are rate limited per IP inside the service."""

from decimal import Decimal

from fastapi import APIRouter, Request

from backend.app.api.deps import DbSession, client_ip
from backend.app.schemas.storefront import OrderCreate, OrderResponse, PayCoin, PublicOffer, StorefrontResponse
from backend.app.services import store_checkout, visitors

router = APIRouter()


def _coin(token) -> PayCoin:
    return PayCoin(asset_id=token.asset_id, symbol=token.symbol, chain=token.blockchain)


@router.get("/{slug}", response_model=StorefrontResponse)
async def get_storefront(slug: str, db: DbSession):
    front = await store_checkout.storefront(db, slug)
    return StorefrontResponse(
        slug=front.store.slug, name=front.store.name, tagline=front.store.tagline, selling=front.selling,
        offers=[PublicOffer(id=o.id, title=o.title, description=o.description, price_cents=o.price_cents,
                            delivery=o.delivery) for o in front.offers],
        pay_with=[_coin(t) for t in front.pay_with])


async def _order_response(view: store_checkout.OrderView) -> OrderResponse:
    order = view.order
    coin = next((t for t in await store_checkout.pay_options() if t.asset_id == order.pay_asset), None)
    amount = order.pay_amount_raw / Decimal(10) ** coin.decimals if coin else order.pay_amount_raw
    return OrderResponse(
        token=order.public_token, status=order.status, store_name=view.store.name, store_slug=view.store.slug,
        offer_title=view.offer.title, price_cents=order.price_cents, pay_coin=_coin(coin) if coin else None,
        pay_amount=format(amount.normalize(), "f"), deposit_address=order.deposit_address,
        deposit_memo=order.deposit_memo, deposit_expires_at=order.deposit_expires_at, paid_at=order.paid_at,
        delivered_at=order.delivered_at, created_at=order.created_at)


@router.post("/{slug}/orders", response_model=OrderResponse, status_code=201)
async def place_order(slug: str, payload: OrderCreate, request: Request, db: DbSession):
    order = await store_checkout.place_order(db, slug, payload.offer_id, str(payload.email), payload.pay_asset,
                                             visitors.ip_hash(client_ip(request)))
    return await _order_response(await store_checkout.order_view(db, order.public_token))


@router.get("/orders/{token}", response_model=OrderResponse)
async def get_order(token: str, db: DbSession):
    return await _order_response(await store_checkout.order_view(db, token))
