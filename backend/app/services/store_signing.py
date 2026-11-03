"""Going live: the Store's owner signs with their passkey, twice.

1. `agent_create`: the Agent API opens a wallet for the Store under a policy
   built from the team's rules (where money may go, the daily cap).
2. `grant_issue`: the owner lets our backend act for that wallet, within
   that policy. The grant token is made here, stored encrypted, and never
   leaves the backend.

We generate each request, the owner's browser signs it unchanged, and we
submit what it signed. Only the person a request was generated for may
submit it."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.store import StoreIntentType
from backend.app.database.store_models import LaceStore, StoreIntent, StorePayee
from backend.app.services.errors import ConflictError, InvalidInputError, NotFoundError
from backend.app.services.store import get_store
from config import settings
from data_sources.near.agent_api import AgentApi, AgentApiError, Operation, new_grant_credential, new_idempotency_key
from utils.log import logger

GRANT_LABEL = "Thalace Store"
# Money actions a Store's wallet may run in an hour: a burst of sales' payouts.
MAX_ACTIONS_PER_HOUR = 60
# How long a submit waits for the API to finish an owner request.
SUBMIT_WAIT_MS = 20_000
NOT_CONFIGURED = "Stores can't go live on this server yet: its NEAR Intents key isn't set."


def agent_api() -> AgentApi:
    """The client every Store call goes through; tests answer for it."""
    return AgentApi()


def _fernet() -> Fernet:
    if not settings.store_grant_key:
        raise ConflictError(NOT_CONFIGURED)
    return Fernet(settings.store_grant_key.encode())


def encrypt_grant(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt_grant(encrypted: str) -> str:
    """The grant token, for one call to the Agent API. Never log or return it."""
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken:
        logger.error("A Store grant token could not be decrypted: STORE_GRANT_KEY changed?")
        raise ConflictError("The Store's access to its wallet can't be read. Its owner needs to sign again.") from None


def _refusal(exc: AgentApiError) -> ConflictError:
    if exc.code == "not_configured":
        return ConflictError(NOT_CONFIGURED)
    if exc.code == "unreachable":
        return ConflictError("NEAR Intents didn't answer. Try again in a minute.")
    return ConflictError(f"NEAR Intents refused this ({exc.code}).")


@dataclass(frozen=True)
class Passkey:
    credential_id: str
    public_key: str
    rp_id: str
    origin: str


async def _store(db: AsyncSession, lace_id: uuid.UUID) -> LaceStore:
    store = await get_store(db, lace_id)
    if store is None:
        raise NotFoundError("This Lace has no Store yet.")
    return store


async def set_owner(db: AsyncSession, lace_id: uuid.UUID, passkey: Passkey) -> LaceStore:
    """The passkey that will sign for the Store. It must belong to this app's
    own site, and can't change once the Store's wallet exists."""
    store = await _store(db, lace_id)
    if store.agent_id:
        raise ConflictError("The Store's wallet already belongs to a passkey; it can't change.")
    site = urlsplit(settings.frontend_base_url)
    if passkey.origin.rstrip("/") != f"{site.scheme}://{site.netloc}" or passkey.rp_id != site.hostname:
        raise InvalidInputError("That passkey isn't for this site.")
    store.owner_credential_id, store.owner_public_key = passkey.credential_id, passkey.public_key
    store.owner_rp_id, store.owner_origin = passkey.rp_id, passkey.origin.rstrip("/")
    await db.flush()
    return store


def destination(payee: StorePayee) -> dict[str, Any]:
    if payee.route == "transfer":
        return {"action": "transfer", "address": payee.address, "confidential": False}
    return {"action": "withdraw", "chain": payee.chain, "address": payee.address, "memo": payee.memo}


def build_policy(store: LaceStore, payees: list[StorePayee]) -> dict[str, Any]:
    """The rules the owner signs. Money leaves only to the payees, only in the
    Store's settlement asset, and never more than the daily cap. The Lace
    and our backend act inside it and can't change it."""
    return {
        "frozen": False,
        "actions": ["transfer", "withdraw"],
        "confidential": False,
        "owner_approval": False,
        "assets": [store.settlement_asset],
        "max_actions_per_hour": MAX_ACTIONS_PER_HOUR,
        "destinations": {"mode": "only", "list": [destination(p) for p in payees]},
        "budget": {"daily_usd": str(store.daily_budget_usd), "weekly_usd": None, "monthly_usd": None},
        "timelock_ms": 0,
    }


@dataclass(frozen=True)
class PendingSignature:
    """What the owner's browser gets: the request to sign, and what it means."""
    correlation_id: str
    type: StoreIntentType
    intent: dict[str, Any]
    preview: dict[str, Any]
    expires_at: datetime


def next_signature(store: LaceStore) -> StoreIntentType | None:
    """What going live still needs from the owner, if anything."""
    if store.agent_id is None:
        return "agent_create"
    if store.grant_id is None:
        return "grant_issue"
    return None


async def request_signature(db: AsyncSession, lace_id: uuid.UUID, user_id: uuid.UUID) -> PendingSignature:
    """Generate the next request the owner signs to take the Store live."""
    store = await _store(db, lace_id)
    kind = next_signature(store)
    if kind is None:
        raise ConflictError("The Store is already live.")
    if not store.owner_public_key:
        raise ConflictError("Add the passkey that signs for the Store first.")
    token_enc = None
    if kind == "agent_create":
        payees = list((await db.scalars(select(StorePayee).where(StorePayee.store_id == store.id))).all())
        fields = {"name": store.name, "external_user_id": str(store.id), "policy": build_policy(store, payees),
                  "owner": {"type": "passkey", "credential_id": store.owner_credential_id,
                            "public_key": store.owner_public_key, "rp_id": store.owner_rp_id,
                            "origin": store.owner_origin}}
    else:
        token, commitment = new_grant_credential()
        token_enc = encrypt_grant(token)
        expires = datetime.now(UTC) + timedelta(days=settings.store_grant_days)
        fields = {"agent_id": store.agent_id, "label": GRANT_LABEL, "credential": commitment,
                  "expires_at": expires.isoformat().replace("+00:00", "Z")}
    try:
        generated = await agent_api().generate_intent(kind, fields,
                                                      idempotency_key=new_idempotency_key(f"{kind}:{store.id}"))
    except AgentApiError as exc:
        raise _refusal(exc) from exc
    expires_at = datetime.fromisoformat(generated.expires_at.replace("Z", "+00:00"))
    db.add(StoreIntent(store_id=store.id, correlation_id=generated.correlation_id, type=kind,
                       requested_by=user_id, grant_token_enc=token_enc, expires_at=expires_at))
    await db.flush()
    return PendingSignature(correlation_id=generated.correlation_id, type=kind, intent=generated.intent,
                            preview=generated.preview, expires_at=expires_at)


async def _intent(db: AsyncSession, store: LaceStore, correlation_id: str, user_id: uuid.UUID) -> StoreIntent:
    row = await db.scalar(select(StoreIntent).where(StoreIntent.correlation_id == correlation_id,
                                                    StoreIntent.store_id == store.id))
    # Someone else's request reads as missing, like any resource that isn't yours.
    if row is None or row.requested_by != user_id:
        raise NotFoundError("No such signature request.")
    return row


async def _apply_create(store: LaceStore, op: Operation) -> None:
    store.agent_id = op.agent_id or op.details.get("agent_id")
    store.policy_revision = op.details.get("revision")
    try:
        agent = await agent_api().agent(store.agent_id)
    except AgentApiError:
        # The wallet exists; its address is read again on the next refresh.
        logger.warning("Store %s: agent %s created but not read back", store.id, store.agent_id)
        return
    store.wallet_account_id = (agent.get("wallet") or {}).get("near_account_id")
    store.owner_account_id = (agent.get("owner_account") or {}).get("account_id")


def _apply_grant(store: LaceStore, row: StoreIntent, op: Operation) -> None:
    grant = op.details.get("grant") or {}
    store.grant_id = grant.get("grant_id")
    store.grant_token_enc, row.grant_token_enc = row.grant_token_enc, None
    expires = grant.get("expires_at")
    store.grant_expires_at = datetime.fromisoformat(expires.replace("Z", "+00:00")) if expires else None
    store.status, store.live_since = "live", datetime.now(UTC)


async def _settle(db: AsyncSession, store: LaceStore, row: StoreIntent, op: Operation) -> None:
    """Record a finished owner request: its effect on the Store, or why it failed."""
    if not op.final:
        return
    row.completed_at = datetime.now(UTC)
    if op.status != "SUCCESS":
        row.status, row.failure_code, row.grant_token_enc = "failed", op.failure_code or op.status.lower(), None
    else:
        row.status = "succeeded"
        if row.type == "agent_create":
            await _apply_create(store, op)
        elif row.type == "grant_issue":
            _apply_grant(store, row, op)
    await db.flush()


async def submit_signature(db: AsyncSession, lace_id: uuid.UUID, user_id: uuid.UUID, correlation_id: str,
                           signed_data: dict[str, Any]) -> tuple[LaceStore, StoreIntent]:
    store = await _store(db, lace_id)
    row = await _intent(db, store, correlation_id, user_id)
    if row.status != "awaiting_signature":
        raise ConflictError("This request was already submitted.")
    if row.expires_at <= datetime.now(UTC):
        row.status, row.grant_token_enc = "expired", None
        await db.flush()
        raise ConflictError("The time to sign ran out. Start again.")
    api = agent_api()
    try:
        await api.submit_intent(row.type, correlation_id, signed_data)
        row.status = "submitted"
        await db.flush()
        await _settle(db, store, row, await api.status(correlation_id, wait_ms=SUBMIT_WAIT_MS))
    except AgentApiError as exc:
        raise _refusal(exc) from exc
    return store, row


async def refresh_signature(db: AsyncSession, lace_id: uuid.UUID, user_id: uuid.UUID,
                            correlation_id: str) -> tuple[LaceStore, StoreIntent]:
    """Where a submitted request stands, settling it once the API has."""
    store = await _store(db, lace_id)
    row = await _intent(db, store, correlation_id, user_id)
    if row.status == "submitted":
        try:
            await _settle(db, store, row, await agent_api().status(correlation_id))
        except AgentApiError as exc:
            raise _refusal(exc) from exc
    return store, row
