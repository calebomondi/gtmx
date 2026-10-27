"""A member's own private finds: they rename one, reword it, leave the
reviewer a note, or remove it; the team's review shows what it is, its
link and that note."""

import psycopg

from backend.tests.helpers import make_user
from backend.tests.test_lace_find_reviews import WANJIRU, _decide, _mine, _push, team  # noqa: F401 -- fixture
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_lace_private_finds import _seed
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings


def _edit(client, lace_id, find, **changes):
    return client.patch(f"{API}/laces/{lace_id}/my-finds/{find['kind']}/{find['id']}", json=changes)


def _remove(client, lace_id, find):
    return client.delete(f"{API}/laces/{lace_id}/my-finds/{find['kind']}/{find['id']}")


def test_the_review_shows_what_it_is_its_link_and_the_note(client, user, team):  # noqa: F811
    client.portal.call(_seed, team, WANJIRU.id)
    client.sign_in(WANJIRU)
    mine = _mine(client, team)
    for name, about in (("Rival", "Scheduling for clinics"), ("Acme", "Runs 40 clinics"), ("Demo Day", "Health buyers")):
        assert _edit(client, team, mine[name], summary=about, note=f"Why {name}").status_code == 200
    _push(client, team, *mine.values())

    client.sign_in(user)
    waiting = {f["name"]: f for f in client.get(f"{API}/laces/{team}/reviews").json()}
    assert {(n, f["summary"], f["link"], f["push_note"]) for n, f in waiting.items()} == {
        ("Rival", "Scheduling for clinics", "https://rival.test/", "Why Rival"),
        ("Acme", "Runs 40 clinics", None, "Why Acme"),
        ("Demo Day", "Health buyers", "https://demo.test/", "Why Demo Day"),
    }
    # Once the team has it, the note has done its job.
    _decide(client, team, waiting["Rival"], "approve")
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT push_note FROM lace_competitors WHERE owner_id IS NULL").fetchall() == [(None,)]


def test_only_what_is_sent_changes(client, team):  # noqa: F811
    client.portal.call(_seed, team, WANJIRU.id)
    client.sign_in(WANJIRU)
    acme = _mine(client, team)["Acme"]
    edited = _edit(client, team, acme, name=" Acme Clinics ", summary="Runs 40 clinics").json()
    assert (edited["name"], edited["summary"], edited["push_note"]) == ("Acme Clinics", "Runs 40 clinics", None)
    edited = _edit(client, team, acme, note="Met them at the expo").json()
    assert (edited["name"], edited["summary"], edited["push_note"]) == ("Acme Clinics", "Runs 40 clinics",
                                                                        "Met them at the expo")
    edited = _edit(client, team, acme, summary="  ", note=None).json()
    assert (edited["summary"], edited["push_note"]) == (None, None)
    assert _edit(client, team, acme, name=" ").status_code == 422
    assert _edit(client, team, acme, note="x" * 501).status_code == 422


def test_removing_takes_it_off_the_list(client, team):  # noqa: F811
    client.portal.call(_seed, team, WANJIRU.id)
    client.sign_in(WANJIRU)
    mine = _mine(client, team)
    assert _remove(client, team, mine["Demo Day"]).status_code == 204
    assert set(_mine(client, team)) == {"Rival", "Acme"}
    assert _remove(client, team, mine["Demo Day"]).status_code == 404
    assert _edit(client, team, mine["Demo Day"], note="hi").status_code == 404


def test_a_find_waiting_for_review_is_locked(client, team):  # noqa: F811
    client.portal.call(_seed, team, WANJIRU.id)
    client.sign_in(WANJIRU)
    rival = _mine(client, team)["Rival"]
    _push(client, team, rival)
    assert _edit(client, team, rival, note="one more thing").status_code == 409
    assert _remove(client, team, rival).status_code == 409


def test_nobody_changes_someone_else_s_finds(client, user, team):  # noqa: F811
    client.portal.call(_seed, team, WANJIRU.id)
    client.sign_in(WANJIRU)
    rival = _mine(client, team)["Rival"]
    client.sign_in(user)
    assert _edit(client, team, rival, name="Mine now").status_code == 404
    assert _remove(client, team, rival).status_code == 404
    stranger = make_user("Stranger")
    client.sign_in(stranger)
    assert _edit(client, team, rival, name="Mine now").status_code == 404
