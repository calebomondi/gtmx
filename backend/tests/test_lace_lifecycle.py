"""Archiving, restoring and deleting a Lace, and trying its onboarding again
after it failed."""

import uuid

import psycopg

from backend.app.runs import lace as lace_runs
from backend.app.services import connections as connection_service
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status
from config import settings


def _sidebar(client) -> list[str]:
    return [row["id"] for row in client.get(f"{API}/laces").json()]


def _set_run_running(lace_id: str) -> None:
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) SELECT %s, user_id, id, 'lace_monitor',"
                     " 'running' FROM laces WHERE id = %s", (uuid.uuid4(), lace_id))


def test_archive_hides_the_lace_and_restore_brings_it_back(client, lace):  # noqa: F811
    archived = client.post(f"{API}/laces/{lace}/archive").json()
    assert archived["status"] == "archived" and lace not in _sidebar(client)
    assert [row["id"] for row in client.get(f"{API}/laces/archived").json()] == [lace]
    # It does no work while archived.
    response = client.post(f"{API}/laces/{lace}/messages", json={"text": "hello?"})
    assert response.status_code == 409 and "Restore" in response.json()["detail"]

    # It finished onboarding, so it comes back active.
    assert client.post(f"{API}/laces/{lace}/restore").json()["status"] == "active"
    assert lace in _sidebar(client) and client.get(f"{API}/laces/archived").json() == []


def test_a_working_lace_cannot_be_archived_or_deleted(client, lace):  # noqa: F811
    _set_run_running(lace)
    assert client.post(f"{API}/laces/{lace}/archive").status_code == 409
    assert client.delete(f"{API}/laces/{lace}").status_code == 409


def test_delete_removes_the_lace_its_findings_and_its_conversation(client, lace, lace_runtime, monkeypatch):  # noqa: F811
    checkpointer = lace_runs.get_checkpointer()
    config = lace_runs.LaceThread(uuid.UUID(lace)).config
    assert client.portal.call(checkpointer.aget_tuple, config) is not None
    revoked = []

    async def remove_all(entity):
        revoked.append(entity)
    monkeypatch.setattr(connection_service, "remove_all", remove_all)

    assert client.delete(f"{API}/laces/{lace}").status_code == 204
    assert revoked == [f"lace:{lace}"]  # its own app accounts go with it
    assert client.get(f"{API}/laces/{lace}").status_code == 404
    assert client.portal.call(checkpointer.aget_tuple, config) is None
    with psycopg.connect(settings.database_url) as conn:
        assert conn.execute("SELECT count(*) FROM lace_facts").fetchone()[0] == 0
        # Runs stay, unlinked, as the record of what they cost.
        assert conn.execute("SELECT count(*), count(lace_id) FROM runs").fetchone() == (1, 0)


def test_another_users_lace_cannot_be_archived_or_deleted(client, lace):  # noqa: F811
    client.sign_in(make_user("Intruder"))
    assert client.post(f"{API}/laces/{lace}/archive").status_code == 404
    assert client.delete(f"{API}/laces/{lace}").status_code == 404


def test_a_failed_onboarding_can_be_tried_again(client, lace_runtime, monkeypatch):  # noqa: F811
    real_onboard = lace_runs.onboard

    async def failing_onboard(store, cfg, progress):
        await real_onboard(store, cfg, progress)  # saves its fact, then fails
        raise RuntimeError("model down")
    monkeypatch.setattr(lace_runs, "onboard", failing_onboard)
    body = client.post(f"{API}/laces", json={"name": "Shanga", "website": "acme.test"}).json()
    lace_id = body["lace"]["id"]
    client.portal.call(_wait_for_status, uuid.UUID(body["run_id"]), {"failed"})
    assert client.get(f"{API}/laces/{lace_id}").json()["status"] == "onboarding"

    monkeypatch.setattr(lace_runs, "onboard", real_onboard)
    retry = client.post(f"{API}/laces/{lace_id}/onboarding")
    assert retry.status_code == 202
    client.portal.call(_wait_for_status, uuid.UUID(retry.json()["run_id"]), {"completed"})
    assert client.get(f"{API}/laces/{lace_id}").json()["status"] == "active"
    # The first attempt's fact was cleared, not recorded twice.
    assert [f["claim"] for f in client.get(f"{API}/laces/{lace_id}/facts").json()] == ["Acme sells payroll to clinics."]
    # Once onboarded, there is nothing to try again.
    assert client.post(f"{API}/laces/{lace_id}/onboarding").status_code == 409
