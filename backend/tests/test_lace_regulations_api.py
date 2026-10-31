"""The regulations API: a member confirms where the startup is registered and
operates, lists the team's regulations and tracks or dismisses them; another
member's private finds stay out of reach."""

import uuid

from sqlalchemy import select

from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import LaceRegulation
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_lace_regulations import WANJIRU, _add
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture


def test_a_member_confirms_where_the_startup_is(client, lace):  # noqa: F811
    path = f"{API}/laces/{lace}/jurisdiction"
    assert client.get(path).json() == {"registered_in": None, "operates_in": [], "jurisdiction_confirmed_at": None}
    saved = client.put(path, json={"registered_in": "KE", "operates_in": ["KE", "UG", "KE"]})
    assert saved.status_code == 200
    body = saved.json()
    assert body["registered_in"] == "KE" and body["operates_in"] == ["KE", "UG"] and body["jurisdiction_confirmed_at"]
    assert client.get(path).json() == body


def test_only_iso_codes_are_accepted(client, lace):  # noqa: F811
    path = f"{API}/laces/{lace}/jurisdiction"
    for payload in ({"registered_in": "Kenya"}, {"operates_in": ["ke"]}, {"operates_in": [f"K{c}" for c in "ABCDEFGHIJK"]}):
        assert client.put(path, json=payload).status_code == 422
    assert client.get(path).json()["jurisdiction_confirmed_at"] is None


def test_regulations_are_listed_and_tracked(client, lace):  # noqa: F811
    client.portal.call(_add, lace)
    path = f"{API}/laces/{lace}/regulations"
    assert client.get(path).json() == []  # nothing tracked yet
    [bill] = client.get(path, params={"status": "suggested"}).json()
    assert bill["kind"] == "bill" and bill["stage"] == "first_reading" and bill["jurisdiction"] == "KE"

    tracked = client.patch(f"{path}/{bill['id']}", json={"status": "tracked"})
    assert tracked.status_code == 200 and tracked.json()["status"] == "tracked"
    assert [r["id"] for r in client.get(path).json()] == [bill["id"]]
    assert client.patch(f"{path}/{bill['id']}", json={"status": "suggested"}).status_code == 422
    assert client.patch(f"{path}/{uuid.uuid4()}", json={"status": "dismissed"}).status_code == 404


def test_another_members_private_find_is_out_of_reach(client, lace):  # noqa: F811
    client.portal.call(_add, lace, {"owner_id": WANJIRU.id})
    path = f"{API}/laces/{lace}/regulations"
    assert client.get(path, params={"status": "suggested"}).json() == []

    async def private_id():
        async with AsyncSessionLocal() as db:
            return await db.scalar(select(LaceRegulation.id).where(LaceRegulation.lace_id == uuid.UUID(lace)))
    assert client.patch(f"{path}/{client.portal.call(private_id)}", json={"status": "tracked"}).status_code == 404
