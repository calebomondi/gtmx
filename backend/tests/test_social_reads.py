"""The founder's public X and TikTok, read by the handle saved in a Lace's
settings: how their posts did, and their TikTok comments as a job."""

import json
import uuid

import psycopg
import pytest

from agents.lace.apps import AppError
from agents.lace.store import JobBlocked
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import social_jobs
from backend.app.services import lace_apps
from backend.tests.helpers import stub_accounts
from backend.tests.test_lace_apps import _lace
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from config import settings
from data_sources.socials.brightdata import SocialsError

VIDEO = {"url": "https://tiktok.com/@shanga.labs/video/7", "text": "Sensors", "date": "2026-10-02", "views": 900,
         "likes": 30, "comments": 2, "shares": 1}


def _handle(lace_id, platform, handle):
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO lace_apps (id, lace_id, platform, enabled, settings) VALUES (%s, %s, %s, true, %s)",
                     (uuid.uuid4(), lace_id, platform, json.dumps({"handle": handle})))


def test_a_handle_is_saved_from_a_link_or_an_at(client, lace, lace_runtime, monkeypatch):  # noqa: F811
    stub_accounts(monkeypatch, set())
    saved = client.put(f"{API}/laces/{lace}/apps/tiktok",
                       json={"settings": {"handle": "https://www.tiktok.com/@shanga.labs"}}).json()
    assert saved["settings"] == {"handle": "shanga.labs"}
    assert client.put(f"{API}/laces/{lace}/apps/x", json={"settings": {"handle": "@Shanga_HQ"}}).json()["settings"] == {
        "handle": "Shanga_HQ"}
    refused = client.put(f"{API}/laces/{lace}/apps/x", json={"settings": {"handle": "not a handle!"}})
    assert refused.status_code == 422 and "e.g. @acme" in refused.json()["detail"]


async def test_my_posts_reads_by_the_saved_handle(monkeypatch):
    lace_id = _lace()
    apps = lace_apps.DbLaceApps(AsyncSessionLocal, lace_id)
    assert await apps.my_posts("tiktok") is None  # no handle yet
    _handle(lace_id, "tiktok", "shanga.labs")
    asked = []
    monkeypatch.setattr(lace_apps, "tiktok_videos", lambda handle, cfg, t: asked.append(handle) or [VIDEO])
    assert await apps.my_posts("tiktok") == [VIDEO] and asked == ["shanga.labs"]

    def fails(*a):
        raise SocialsError("timeout")
    monkeypatch.setattr(lace_apps, "tiktok_videos", fails)
    with pytest.raises(AppError, match="Couldn't read @shanga.labs on TikTok"):
        await apps.my_posts("tiktok")


def _run(lace_id) -> uuid.UUID:
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        return conn.execute("INSERT INTO runs (id, user_id, lace_id, kind, status) VALUES (%s, %s, %s, 'lace_comments',"
                            " 'running') RETURNING id", (uuid.uuid4(), uuid.uuid4(), lace_id)).fetchone()[0]


def _feed(lace_id) -> list[tuple]:
    with psycopg.connect(settings.database_url) as conn:
        return conn.execute("SELECT kind, title, summary FROM lace_activity WHERE lace_id = %s", (lace_id,)).fetchall()


async def test_the_comments_job_reads_videos_with_comments(monkeypatch):
    lace_id = _lace()
    _handle(lace_id, "tiktok", "shanga.labs")
    quiet = {**VIDEO, "url": "https://tiktok.com/@shanga.labs/video/8", "comments": None}
    monkeypatch.setattr(social_jobs.tiktok, "recent_videos", lambda *a: [quiet, VIDEO])
    monkeypatch.setattr(social_jobs.tiktok, "video_comments",
                        lambda url, cfg, t: [{"author": "farmer_joe", "text": "What does it cost?", "date": None,
                                              "likes": 2}])
    await social_jobs.tiktok_comments_job(_run(lace_id), lace_id, {"videos": 3})
    assert _feed(lace_id) == [("comments_read", "Read 1 TikTok comment", "On 1 video of @shanga.labs")]
    with psycopg.connect(settings.database_url) as conn:
        update = conn.execute("SELECT text FROM lace_events WHERE lace_id = %s", (lace_id,)).fetchone()[0]
    assert "@farmer_joe: What does it cost?" in update and "video/8" not in update


async def test_the_comments_job_without_a_handle_says_how_to_fix_it():
    lace_id = _lace()
    with pytest.raises(JobBlocked):
        await social_jobs.tiktok_comments_job(_run(lace_id), lace_id, {"videos": 3})
    [(kind, title, summary)] = _feed(lace_id)
    assert (kind, title) == ("job_failed", "The TikTok comment read failed") and "Apps & accounts → TikTok" in summary
