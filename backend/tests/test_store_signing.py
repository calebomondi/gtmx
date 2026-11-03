"""Going live: the Lace's owner adds a passkey for this site, then signs the
Store's wallet into being and grants our backend access, each request
relayed unchanged. The policy holds the team's rules, the grant token is
stored encrypted, and only the person a request was made for submits it."""

import hashlib

import psycopg
import pytest
from cryptography.fernet import Fernet

from backend.app.services import store_signing
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_lace_members import _join
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings
from data_sources.near.agent_api import AgentApiError, GeneratedIntent, Operation

SITE = "https://app.thalace.test"
PASSKEY = {"credential_id": "Y3JlZC0x", "public_key": "M" + "A" * 90, "rp_id": "app.thalace.test", "origin": SITE}
AGENT = "a" * 64


class FakeAgentApi:
    """Answers like the Agent API: each owner request succeeds once submitted."""

    def __init__(self):
        self.generated: list[tuple[str, dict]] = []
        self.submitted: list[tuple[str, str, dict]] = []
        self.refuse: AgentApiError | None = None

    async def generate_intent(self, kind, fields, *, idempotency_key=None):
        if self.refuse:
            raise self.refuse
        self.generated.append((kind, fields))
        return GeneratedIntent(correlation_id=f"intent_{kind}", type=kind, expires_at="2099-01-01T00:00:00Z",
                               intent={"standard": "webauthn", "payload": {"challenge": "abc"}},
                               preview={"summary": f"Sign {kind}"}, agent_id=AGENT if kind == "agent_create" else None)

    async def submit_intent(self, kind, correlation_id, signed_data):
        self.submitted.append((kind, correlation_id, signed_data))

    async def status(self, correlation_id, *, wait_ms=0):
        if correlation_id == "intent_agent_create":
            return Operation(correlation_id, "agent_create", "SUCCESS", agent_id=AGENT, details={"revision": 1})
        return Operation(correlation_id, "grant_issue", "SUCCESS",
                         details={"grant": {"grant_id": "g1", "expires_at": "2027-10-29T00:00:00Z"}})

    async def agent(self, agent_id):
        return {"id": agent_id, "wallet": {"near_account_id": "f00d" * 16},
                "owner_account": {"account_id": "0s" + "1" * 40}}


@pytest.fixture
def agent_api(monkeypatch):
    fake = FakeAgentApi()
    monkeypatch.setattr(store_signing, "agent_api", lambda: fake)
    monkeypatch.setattr(settings, "store_grant_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "frontend_base_url", SITE)
    return fake


def _ready(client, lace_id):  # noqa: F811
    client.put(f"{API}/laces/{lace_id}/store/shown", json={"shown": True})
    client.put(f"{API}/laces/{lace_id}/store/payees", json={"payees": [
        {"label": "Treasury", "route": "transfer", "address": "acme.near", "share_bps": 7000},
        {"label": "Ada", "route": "withdraw", "chain": "base", "address": "0xAbC1", "share_bps": 2000}]})
    return client.put(f"{API}/laces/{lace_id}/store/owner", json=PASSKEY)


def _sign(client, lace_id):  # noqa: F811
    pending = client.post(f"{API}/laces/{lace_id}/store/signatures")
    assert pending.status_code == 201, pending.text
    body = pending.json()
    signed = {**body["intent"], "credential": {"id": "Y3JlZC0x", "response": {"signature": "sig"}}}
    return body, client.post(f"{API}/laces/{lace_id}/store/signatures/{body['correlation_id']}",
                             json={"signed_data": signed})


def _grant_token_enc(lace_id):
    with psycopg.connect(settings.database_url) as conn:
        return conn.execute("SELECT grant_token_enc FROM lace_stores WHERE lace_id = %s", (lace_id,)).fetchone()[0]


def test_two_signatures_take_the_store_live(client, lace, agent_api):  # noqa: F811
    assert _ready(client, lace).json()["has_owner"] is True

    created, done = _sign(client, lace)
    assert created["type"] == "agent_create" and created["preview"]["summary"] == "Sign agent_create"
    assert done.json()["status"] == "succeeded"
    store = done.json()["store"]
    assert (store["status"], store["wallet_account_id"], store["owner_account_id"]) == ("setup", "f00d" * 16,
                                                                                      "0s" + "1" * 40)

    granted, done = _sign(client, lace)
    assert granted["type"] == "grant_issue"
    store = done.json()["store"]
    assert store["status"] == "live" and store["live_since"]
    assert "grant" not in str(store)

    # The owner signed the commitment of the very token we keep, encrypted.
    token = Fernet(settings.store_grant_key.encode()).decrypt(_grant_token_enc(lace).encode()).decode()
    assert token.startswith("ngt_")
    assert agent_api.generated[1][1]["credential"] == hashlib.sha256(token.encode()).hexdigest()
    # The browser's signature went to the API as it was.
    assert agent_api.submitted[0][2]["credential"]["response"]["signature"] == "sig"

    assert client.post(f"{API}/laces/{lace}/store/signatures").status_code == 409


def test_the_policy_holds_the_teams_rules(client, lace, agent_api):  # noqa: F811
    _ready(client, lace)
    _sign(client, lace)
    kind, fields = agent_api.generated[0]
    assert fields["owner"] == {"type": "passkey", **PASSKEY}
    policy = fields["policy"]
    assert policy["destinations"] == {"mode": "only", "list": [
        {"action": "transfer", "address": "acme.near", "confidential": False},
        {"action": "withdraw", "chain": "base", "address": "0xabc1", "memo": None}]}
    assert policy["budget"]["daily_usd"] == "50.00"
    assert policy["assets"] == [settings.store_settlement_asset]
    assert set(policy["actions"]) == {"transfer", "withdraw"}


def test_once_the_wallet_exists_its_rules_and_passkey_are_fixed(client, lace, agent_api):  # noqa: F811
    _ready(client, lace)
    _sign(client, lace)
    assert client.put(f"{API}/laces/{lace}/store/payees", json={"payees": []}).status_code == 409
    assert client.patch(f"{API}/laces/{lace}/store", json={"daily_budget_usd": "10"}).status_code == 409
    assert client.put(f"{API}/laces/{lace}/store/owner", json=PASSKEY).status_code == 409


def test_a_passkey_for_another_site_is_refused(client, lace, agent_api):  # noqa: F811
    client.put(f"{API}/laces/{lace}/store/shown", json={"shown": True})
    other = {**PASSKEY, "origin": "https://evil.test", "rp_id": "evil.test"}
    assert client.put(f"{API}/laces/{lace}/store/owner", json=other).status_code == 422


def test_no_signature_without_a_passkey(client, lace, agent_api):  # noqa: F811
    client.put(f"{API}/laces/{lace}/store/shown", json={"shown": True})
    assert client.post(f"{API}/laces/{lace}/store/signatures").status_code == 409


def test_only_the_owner_signs_and_only_their_own_request(client, lace, agent_api):  # noqa: F811
    _ready(client, lace)
    pending = client.post(f"{API}/laces/{lace}/store/signatures").json()
    admin = make_user("Admin")
    _join(lace, admin, role="admin")
    client.sign_in(admin)
    assert client.post(f"{API}/laces/{lace}/store/signatures").status_code == 403
    assert client.post(f"{API}/laces/{lace}/store/signatures/{pending['correlation_id']}",
                       json={"signed_data": {}}).status_code == 403


def test_a_refusal_from_near_intents_is_a_conflict(client, lace, agent_api):  # noqa: F811
    _ready(client, lace)
    agent_api.refuse = AgentApiError("owner_type_unsupported", status=400)
    refused = client.post(f"{API}/laces/{lace}/store/signatures")
    assert refused.status_code == 409 and "owner_type_unsupported" in refused.text


def test_without_a_grant_key_nothing_goes_live(client, lace, agent_api, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "store_grant_key", "")
    _ready(client, lace)
    _sign(client, lace)
    refused = client.post(f"{API}/laces/{lace}/store/signatures")
    assert refused.status_code == 409 and "isn't set" in refused.text
