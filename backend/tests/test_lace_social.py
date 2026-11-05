"""What a listen keeps for the Social view: the founder's posts with how they
did (refreshed when read again) and what was said, sorted, once each; the
founder marks what they acted on."""

import uuid
from datetime import UTC, datetime

from langchain_core.messages import AIMessage

from agents.schemas.listening import HeardItem
from backend.app.runs import listening_jobs, manager
from backend.app.services.lace_apps import DbLaceApps
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import _wait_for_turns, lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture
from backend.tests.test_runs import _wait_for_status

NOW = datetime.now(UTC).isoformat()


def _listen(client, user, lace_id, monkeypatch, likes: int):
    async def nothing(self, *a):
        return None

    async def comments(self, platform, posts):
        return [{"comment_id": "ig_1", "author": "wanjiru", "text": "Can it find us distributors?",
                 "post_url": "https://instagram.com/p/1", "date": NOW}] if platform == "instagram" else None

    async def posts(self, platform):
        return [{"url": "https://x.com/acme/status/2", "text": "We launched", "date": NOW, "views": 900,
                 "likes": likes, "replies": 3, "reposts": 1}] if platform == "x" else None
    for name in ("x_mentions", "tiktok_comments"):
        monkeypatch.setattr(DbLaceApps, name, nothing)
    monkeypatch.setattr(DbLaceApps, "my_comments", comments)
    monkeypatch.setattr(DbLaceApps, "my_posts", posts)
    monkeypatch.setattr(listening_jobs, "sort_heard", lambda startup, facts, items: [
        (item, HeardItem(ref="1", kind="lead", note="An agritech founder asking")) for item in items])
    run = client.portal.call(manager.start_lace_job, "lace_listening", user.id, uuid.UUID(lace_id), {})
    client.portal.call(_wait_for_status, run.id, {"completed"})


def test_a_listen_keeps_posts_and_what_was_said_once(client, lace, lace_runtime, user, monkeypatch):  # noqa: F811
    lace_runtime.extend(AIMessage(content="Noted.") for _ in range(3))
    _listen(client, user, lace, monkeypatch, likes=12)
    [post] = client.get(f"{API}/laces/{lace}/social/posts").json()
    assert (post["platform"], post["views"], post["likes"], post["comments"], post["shares"]) == ("x", 900, 12, 3, 1)
    [item] = client.get(f"{API}/laces/{lace}/social/heard").json()
    assert (item["platform"], item["author"], item["verdict"], item["note"], item["status"]) == (
        "instagram", "wanjiru", "lead", "An agritech founder asking", "new")
    client.portal.call(_wait_for_turns, lace, 1)

    # Read again: the post's numbers move on; the comment is kept once, as the founder left it.
    assert client.patch(f"{API}/laces/{lace}/social/heard/{item['id']}", json={"status": "done"}).status_code == 200
    _listen(client, user, lace, monkeypatch, likes=40)
    assert [p["likes"] for p in client.get(f"{API}/laces/{lace}/social/posts?platform=x").json()] == [40]
    assert [i["status"] for i in client.get(f"{API}/laces/{lace}/social/heard").json()] == ["done"]
    assert client.get(f"{API}/laces/{lace}/social/heard?status=new").json() == []


def test_social_is_private_and_bounded(client, lace):  # noqa: F811
    assert client.get(f"{API}/laces/{lace}/social/posts?limit=500").status_code == 422
    assert client.get(f"{API}/laces/{lace}/social/heard?platform=myspace").status_code == 422
    client.sign_in(make_user("Intruder"))
    assert client.get(f"{API}/laces/{lace}/social/heard").status_code == 404
    assert client.patch(f"{API}/laces/{lace}/social/heard/{uuid.uuid4()}", json={"status": "done"}).status_code == 404
