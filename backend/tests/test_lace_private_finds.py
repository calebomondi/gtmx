"""A member's private finds (owner_id set): keyed apart from the team's, and
never shown on any of the team's surfaces (lists, counts, search, the brief,
the Lace's alert) until they are pushed to the team."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import LaceAccount, LaceCompetitor, LaceOpportunity
from backend.app.services import lace_briefs, lace_competitors
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import RIVAL, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture

WANJIRU = make_user("Wanjiru")


async def _seed(lace_id: str, owner_id: uuid.UUID | None) -> None:
    """One suggested find of each kind: Rival, Acme and Demo Day."""
    async with AsyncSessionLocal() as db:
        db.add_all([
            LaceCompetitor(lace_id=lace_id, owner_id=owner_id, name="Rival", website="https://rival.test/",
                           domain_key="rival.test", status="suggested"),
            LaceAccount(lace_id=lace_id, owner_id=owner_id, key="acme.test", name="Acme", account_type="company",
                        record={}, status="suggested"),
            LaceOpportunity(lace_id=lace_id, owner_id=owner_id, kind="showcase", title="Demo Day",
                            url="https://demo.test/", url_key="demo.test", status="suggested",
                            deadline=date.today() + timedelta(days=3)),
        ])
        await db.commit()


def test_keys_are_unique_per_owner(client, lace):  # noqa: F811
    client.portal.call(_seed, lace, None)
    client.portal.call(_seed, lace, WANJIRU.id)
    for owner in (None, WANJIRU.id):
        with pytest.raises(IntegrityError):
            client.portal.call(_seed, lace, owner)


def test_the_team_never_sees_a_private_find(client, lace):  # noqa: F811
    client.portal.call(_seed, lace, WANJIRU.id)
    for path, saved in (("competitors", "tracked"), ("accounts", "target"), ("opportunities", "open")):
        for status in ("suggested", saved, "dismissed"):
            assert client.get(f"{API}/laces/{lace}/{path}", params={"status": status}).json() == []
    for term in ("Rival", "Acme", "Demo"):
        hits = client.get(f"{API}/laces/search", params={"q": term}).json()
        assert [h for h in hits if h["kind"] in ("competitor", "account", "opportunity")] == []
    assert client.get(f"{API}/laces").json()[0]["mood"] is None

    async def team_views():
        async with AsyncSessionLocal() as db:
            since = datetime.now(UTC) - timedelta(days=1)
            return (await lace_briefs.suggestion_counts(db, uuid.UUID(lace)),
                    await lace_briefs.digest(db, uuid.UUID(lace), since, date.today()))
    counts, digest = client.portal.call(team_views)
    assert counts == {"competitors": 0, "accounts": 0, "opportunities": 0}
    assert not any(name in digest for name in ("Rival", "Acme", "Demo Day"))

    # The same finds, the team's: now every surface shows them.
    client.portal.call(_seed, lace, None)
    counts, digest = client.portal.call(team_views)
    assert counts == {"competitors": 1, "accounts": 1, "opportunities": 1}
    assert all(name in digest for name in ("Rival", "Acme", "Demo Day"))
    assert client.get(f"{API}/laces").json()[0]["mood"] == "alert"
    assert {h["kind"] for h in client.get(f"{API}/laces/search", params={"q": "Rival"}).json()} >= {"competitor"}


def test_a_private_find_cannot_be_saved_for_the_team(client, lace):  # noqa: F811
    client.portal.call(_seed, lace, WANJIRU.id)

    async def private_rival():
        async with AsyncSessionLocal() as db:
            return await db.scalar(LaceCompetitor.__table__.select().with_only_columns(LaceCompetitor.id))
    rival = client.portal.call(private_rival)
    assert client.patch(f"{API}/laces/{lace}/competitors/{rival}", json={"status": "tracked"}).status_code == 404


def test_a_team_search_files_its_own_copy(client, lace):  # noqa: F811
    client.portal.call(_seed, lace, WANJIRU.id)

    async def hunt():
        async with AsyncSessionLocal() as db:
            found = await lace_competitors.upsert_found(db, uuid.UUID(lace), None, [RIVAL])
            await db.commit()
            return found
    assert client.portal.call(hunt) == (1, 0)
    [team] = client.get(f"{API}/laces/{lace}/competitors", params={"status": "suggested"}).json()
    assert team["name"] == "Rival"
