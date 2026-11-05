"""A Lace's connected apps: X lookups go through the owner's live X
connection; no connection means no lookup, and a refusal is an AppError."""

import uuid

import psycopg
import pytest

from agents.lace.apps import AppError
from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import lace_apps
from config import settings
from backend.tests.helpers import stub_accounts


def _lace() -> uuid.UUID:
    user_id = uuid.uuid4()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        return conn.execute("INSERT INTO laces (id, user_id, name, website) VALUES (%s, %s, 'Ada', 'https://acme.test')"
                            " RETURNING id", (uuid.uuid4(), user_id)).fetchone()[0]


def _connections(monkeypatch, platforms):
    stub_accounts(monkeypatch, set(platforms))


async def test_x_lookups_use_the_owners_live_x(monkeypatch):
    _connections(monkeypatch, ["gmail", "x"])
    calls = []

    def execute(user_id, tool, arguments, connection_id):
        calls.append((tool, arguments["username"], connection_id))
        return {"data": {"data": {"username": "acme"}}, "error": None, "log_id": "l1"}
    monkeypatch.setattr(lace_apps.connection_service, "execute_tool", execute)
    apps = lace_apps.DbLaceApps(AsyncSessionLocal, _lace())
    assert await apps.x("profile", "acme") == {"data": {"username": "acme"}}
    assert calls == [("TWITTER_USER_LOOKUP_BY_USERNAME", "acme", "ca_x")]


async def test_no_x_connection_means_no_lookup(monkeypatch):
    _connections(monkeypatch, ["gmail"])
    monkeypatch.setattr(lace_apps.connection_service, "execute_tool", lambda *a: pytest.fail("not connected"))
    assert await lace_apps.DbLaceApps(AsyncSessionLocal, _lace()).x("post", "42") is None


async def test_a_refused_or_failed_lookup_is_an_app_error(monkeypatch):
    _connections(monkeypatch, ["x"])
    apps = lace_apps.DbLaceApps(AsyncSessionLocal, _lace())
    monkeypatch.setattr(lace_apps.connection_service, "execute_tool",
                        lambda *a: {"data": None, "error": "429 Too Many Requests", "log_id": None})
    with pytest.raises(AppError, match="429"):
        await apps.x("profile", "acme")

    def boom(*a):
        raise ConnectionError("reset")
    monkeypatch.setattr(lace_apps.connection_service, "execute_tool", boom)
    with pytest.raises(AppError, match="ConnectionError"):
        await apps.x("profile", "acme")


async def test_reading_facebook_comments_names_the_pages_to_pick_from(monkeypatch):
    _connections(monkeypatch, ["facebook"])
    pages = {"data": [{"id": "1", "name": "sociokritic"}, {"id": "2", "name": "Zendawa Africa"}]}
    monkeypatch.setattr(lace_apps.connection_service, "execute_tool",
                        lambda *a: {"data": pages, "error": None, "log_id": "l"})
    apps = lace_apps.DbLaceApps(AsyncSessionLocal, _lace())
    with pytest.raises(AppError, match=r"manages 2 Pages \(sociokritic, Zendawa Africa\).*ask_to_link"):
        await apps.my_comments("facebook", 5)
    pages["data"] = []
    with pytest.raises(AppError, match="manages no Page"):
        await apps.my_comments("facebook", 5)


def _with_page(page: str):
    async def live(self, platform):
        return lace_apps._Live("founder", f"ca_{platform}", page)
    return live


async def test_facebook_comments_come_inside_the_linked_pages_posts(monkeypatch):
    _connections(monkeypatch, ["facebook"])
    calls = []
    posts = {"data": [
        {"id": "p_1", "message": "Flu doesn't wait.", "permalink_url": "https://facebook.com/p_1",
         "comments": {"data": [{"id": "c_1", "message": "Do you deliver to Nakuru?", "from": {"name": "Amina"},
                                "created_time": "2026-11-05T10:00:00+0000"},
                               {"id": "c_2", "message": "", "from": {"name": "Sticker"}}]}},
        {"id": "p_2", "message": "No comments here"}]}

    def execute(entity, tool, arguments, connection_id):
        calls.append((tool, arguments))
        return {"data": posts, "error": None, "log_id": "l"}
    monkeypatch.setattr(lace_apps.connection_service, "execute_tool", execute)
    monkeypatch.setattr(lace_apps.DbLaceApps, "_live", _with_page("pg_1"))
    found = await lace_apps.DbLaceApps(AsyncSessionLocal, _lace()).my_comments("facebook", 5)
    assert [(c["author"], c["text"]) for c in found] == [("Amina", "Do you deliver to Nakuru?")]
    # One call, with the Page's token: no separate comments call, which Facebook refuses.
    [(tool, arguments)] = calls
    assert tool == "FACEBOOK_GET_PAGE_POSTS" and arguments["page_id"] == "pg_1"
    assert "comments.limit(" in arguments["fields"]
