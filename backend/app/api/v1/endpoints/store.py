"""A Lace's Store while the team sets it up: its tab, its details, what it
sells and who shares in each sale. Members see it; admins and the owner
change it."""

import uuid

from fastapi import APIRouter

from backend.app.api.deps import AdminLace, CurrentUser, DbSession, MemberLace, OwnerLace
from backend.app.schemas.store import (OfferCreate, OfferResponse, OfferUpdate, PasskeyOwner, PayeeResponse,
                                       PayeesUpdate, SignatureRequest, SignatureStatus, SignedRequest, StoreResponse,
                                       StoreShownRequest, StoreUpdate)
from backend.app.services import store, store_signing

router = APIRouter()


@router.get("/{lace_id}/store", response_model=StoreResponse | None)
async def get_store(lace: MemberLace, db: DbSession):
    """The Lace's Store, or null before anyone turned it on."""
    return await store.get_store(db, lace.id)


@router.put("/{lace_id}/store/shown", response_model=StoreResponse)
async def set_shown(lace: AdminLace, payload: StoreShownRequest, db: DbSession):
    """Show or hide the Store's tab; the first time, this makes the Store."""
    row = await store.set_shown(db, lace, payload.shown)
    await db.commit()
    return row


@router.patch("/{lace_id}/store", response_model=StoreResponse)
async def update_store(lace: AdminLace, payload: StoreUpdate, db: DbSession):
    row = await store.update_details(db, lace.id, **payload.model_dump(exclude_unset=True))
    await db.commit()
    return row


@router.get("/{lace_id}/store/offers", response_model=list[OfferResponse])
async def list_offers(lace: MemberLace, db: DbSession):
    return await store.list_offers(db, lace.id)


@router.post("/{lace_id}/store/offers", response_model=OfferResponse, status_code=201)
async def add_offer(lace: AdminLace, payload: OfferCreate, user: CurrentUser, db: DbSession):
    offer = await store.add_offer(db, lace.id, payload.model_dump(mode="json"), user.id)
    await db.commit()
    return offer


@router.patch("/{lace_id}/store/offers/{offer_id}", response_model=OfferResponse)
async def update_offer(lace: AdminLace, offer_id: uuid.UUID, payload: OfferUpdate, db: DbSession):
    offer = await store.update_offer(db, lace.id, offer_id, payload.model_dump(mode="json", exclude_unset=True))
    await db.commit()
    return offer


@router.get("/{lace_id}/store/payees", response_model=list[PayeeResponse])
async def list_payees(lace: MemberLace, db: DbSession):
    return await store.list_payees(db, lace.id)


@router.put("/{lace_id}/store/payees", response_model=list[PayeeResponse])
async def set_payees(lace: AdminLace, payload: PayeesUpdate, db: DbSession):
    """Replace the revenue split, while the Store is still being set up."""
    rows = await store.set_payees(db, lace.id, [p.model_dump() for p in payload.payees])
    await db.commit()
    return rows


# -- Going live: the owner signs with their passkey --

@router.put("/{lace_id}/store/owner", response_model=StoreResponse)
async def set_owner(lace: OwnerLace, payload: PasskeyOwner, db: DbSession):
    """The passkey that signs for the Store, before its wallet exists."""
    row = await store_signing.set_owner(db, lace.id, store_signing.Passkey(**payload.model_dump()))
    await db.commit()
    return row


@router.post("/{lace_id}/store/signatures", response_model=SignatureRequest, status_code=201)
async def request_signature(lace: OwnerLace, user: CurrentUser, db: DbSession):
    """The next request the owner signs to take the Store live."""
    pending = await store_signing.request_signature(db, lace.id, user.id)
    await db.commit()
    return pending


def _status(store_row, intent) -> SignatureStatus:
    return SignatureStatus(correlation_id=intent.correlation_id, type=intent.type, status=intent.status,
                           failure_code=intent.failure_code, store=StoreResponse.model_validate(store_row))


@router.post("/{lace_id}/store/signatures/{correlation_id}", response_model=SignatureStatus)
async def submit_signature(lace: OwnerLace, correlation_id: str, payload: SignedRequest, user: CurrentUser,
                           db: DbSession):
    store_row, intent = await store_signing.submit_signature(db, lace.id, user.id, correlation_id, payload.signed_data)
    await db.commit()
    return _status(store_row, intent)


@router.get("/{lace_id}/store/signatures/{correlation_id}", response_model=SignatureStatus)
async def get_signature(lace: OwnerLace, correlation_id: str, user: CurrentUser, db: DbSession):
    store_row, intent = await store_signing.refresh_signature(db, lace.id, user.id, correlation_id)
    await db.commit()
    return _status(store_row, intent)
