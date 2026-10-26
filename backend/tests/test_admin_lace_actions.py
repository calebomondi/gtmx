"""Admin fixes for duplicate Laces (made before one Lace per domain): the
detail names the Lace holding the domain, the list filters to duplicates,
folding moves the duplicate's people onto the holder and archives it, and
taking the domain swaps which Lace holds it. Both are audited."""

import uuid

import psycopg
import pytest

from backend.tests.helpers import make_user
from backend.tests.test_admin_entities import API, directory  # noqa: F401 -- fixture
from config import settings


def _lace(conn, user_id, name, domain, created_at) -> uuid.UUID:
    lace_id = uuid.uuid4()
    conn.execute("INSERT INTO laces (id, user_id, name, website, domain, status, created_at)"
                 " VALUES (%s, %s, %s, 'https://www.acme.test/', %s, 'active', %s)",
                 (lace_id, user_id, name, domain, created_at))
    return lace_id


def _member(conn, lace_id, user_id, role) -> None:
    conn.execute("INSERT INTO lace_members (id, lace_id, user_id, role, status) VALUES (%s, %s, %s, %s, 'active')",
                 (uuid.uuid4(), lace_id, user_id, role))


@pytest.fixture
def clash(user, directory):  # noqa: F811
    """Acme (the owner's, holding acme.test) and a later Acme Two of zed's,
    with a member of its own, that holds no domain."""
    zed, mo = uuid.UUID(directory[1].id), uuid.uuid4()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        acme = _lace(conn, user.id, "Acme", "acme.test", "2026-10-01")
        _member(conn, acme, user.id, "owner")
        two = _lace(conn, zed, "Acme Two", None, "2026-10-05")
        _member(conn, two, zed, "owner")
        _member(conn, two, mo, "member")
    return {"acme": str(acme), "two": str(two), "zed": zed, "mo": mo}


def _people(lace_id):
    with psycopg.connect(settings.database_url) as conn:
        return dict(conn.execute("SELECT user_id, role FROM lace_members WHERE lace_id = %s AND status = 'active'",
                                 (lace_id,)).fetchall())


def _audit(action):
    with psycopg.connect(settings.database_url) as conn:
        return conn.execute("SELECT target_id, before, after FROM admin_audit_log WHERE action = %s",
                            (action,)).fetchall()


def test_a_duplicate_names_the_lace_holding_its_domain(client, clash):
    detail = client.get(f"{API}/laces/{clash['two']}").json()
    assert (detail["domain_clash"], detail["domain"]) == (True, None)
    assert (detail["clashes_with"]["name"], detail["clashes_with"]["user_email"]) == ("Acme", "owner@example.com")
    assert client.get(f"{API}/laces/{clash['acme']}").json()["clashes_with"] is None
    duplicates = {r["name"] for r in client.get(f"{API}/laces", params={"clash": True}).json()["items"]}
    assert "Acme Two" in duplicates and "Acme" not in duplicates  # (the directory's Lace has no domain either)


def test_folding_moves_its_people_to_the_holder(client, user, clash):
    folded = client.post(f"{API}/laces/{clash['two']}/fold").json()
    assert folded["status"] == "archived"
    assert _people(clash["acme"]) == {user.id: "owner", clash["zed"]: "admin", clash["mo"]: "member"}
    [(target, before, after)] = _audit("lace.fold")
    assert (target, before["status"], after["into"]) == (clash["two"], "active", clash["acme"])
    assert sorted(after["joined"]) == sorted([str(clash["zed"]), str(clash["mo"])])
    assert client.post(f"{API}/laces/{clash['acme']}/fold").status_code == 409  # it holds its domain


def test_folding_waits_for_the_lace_to_finish_working(client, user, clash):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s, 'lace_turn', 'running')",
                     (uuid.uuid4(), clash["zed"], clash["two"]))
    assert client.post(f"{API}/laces/{clash['two']}/fold").status_code == 409
    assert _people(clash["acme"]) == {user.id: "owner"}


def test_taking_the_domain_swaps_which_lace_holds_it(client, clash):
    taken = client.post(f"{API}/laces/{clash['two']}/take-domain").json()
    assert (taken["domain"], taken["domain_clash"], taken["clashes_with"]) == ("acme.test", False, None)
    old = client.get(f"{API}/laces/{clash['acme']}").json()
    assert (old["domain_clash"], old["clashes_with"]["name"]) == (True, "Acme Two")
    [(target, before, after)] = _audit("lace.take_domain")
    assert (target, before["held_by"], after["domain"]) == (clash["two"], clash["acme"], "acme.test")


@pytest.mark.parametrize("action", ["fold", "take-domain"])
def test_fixes_are_admin_only(client, clash, action):
    assert client.post(f"{API}/laces/{uuid.uuid4()}/{action}").status_code == 404
    client.sign_in(make_user("Founder"))
    assert client.post(f"{API}/laces/{clash['two']}/{action}").status_code == 403
