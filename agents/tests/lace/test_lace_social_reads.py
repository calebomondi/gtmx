"""The founder's public X and TikTok, read by handle with nothing connected:
how their posts did (summed in code), and their TikTok comments as a job."""

import json

import pytest

from agents.lace.apps import AppError
from agents.lace.social_stats import summarise_posts
from agents.lace.tools import build_tools
from agents.tests.lace.lace_fakes import MemoryStore, RecordingJobs

POSTS = [{"url": "u1", "text": "Launch", "views": 1200, "likes": 40, "replies": 3},
         {"url": "u2", "text": "Pilot farms", "views": 300, "likes": 12, "replies": None},
         {"url": "u3", "text": "Hiring", "views": 4500, "likes": 90, "replies": 10}]


class Apps:
    def __init__(self, posts=None, error=None):
        self.posts, self.error, self.asked = posts, error, []

    async def my_posts(self, platform):
        self.asked.append(platform)
        if self.error:
            raise AppError(self.error)
        return self.posts


def _tools(settings, apps, jobs=None):
    return {t.name: t for t in build_tools(MemoryStore(), settings, jobs, apps=apps)}


async def _run(tool, **args) -> dict:
    return json.loads(await tool.ainvoke(args))


def test_posts_are_summed_in_code():
    s = summarise_posts(POSTS)
    assert (s["posts"], s["totals"], s["ranked_by"]) == (3, {"views": 6000, "likes": 142, "replies": 13}, "views")
    assert s["averages"] == {"views": 2000.0, "likes": 47.3, "replies": 4.3}
    assert [p["url"] for p in s["best"]] == ["u3", "u1", "u2"]


async def test_how_my_posts_did(settings):
    apps = Apps(POSTS)
    out = await _run(_tools(settings, apps)["how_my_posts_did"], platform="tiktok")
    assert out["ok"] and out["data"]["totals"]["views"] == 6000 and apps.asked == ["tiktok"]


@pytest.mark.parametrize("apps, said", [
    (Apps(None), "No TikTok handle is saved"), (Apps(error="Couldn't read @acme"), "Couldn't read"),
])
async def test_without_a_handle_or_a_read_it_says_why(settings, apps, said):
    out = await _run(_tools(settings, apps)["how_my_posts_did"], platform="tiktok")
    assert not out["ok"] and said in out["error"]


async def test_tiktok_comments_are_read_in_the_background(settings):
    jobs = RecordingJobs()
    tool = _tools(settings, Apps(), jobs)["read_tiktok_comments"]
    assert (await _run(tool, videos=9))["ok"]
    assert jobs.started == [("read_tiktok_comments", {"videos": 5})]  # capped
