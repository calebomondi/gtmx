"""Background reads of the founder's own public social accounts, by the handle
saved in the Lace's settings (nothing connected): the comments on their
recent TikTok videos, whose scraper is too slow for a turn. What was read
goes to the Lace as an update and to the Feed."""

import asyncio
import uuid
from datetime import UTC, datetime

from agents.lace.store import JobBlocked
from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import events
from backend.app.runs.lace_jobs import report_failure
from backend.app.services import lace_activity, lace_events
from backend.app.services.lace_activity import plural
from backend.app.services.lace_apps import DbLaceApps
from backend.app.services.runs import set_run_fields
from config import settings
from data_sources.socials import tiktok

# Comments kept per video, and how much of each the Lace reads.
COMMENTS_PER_VIDEO = 25
_NO_HANDLE = ("No TikTok handle is saved for this Lace. Add it under Apps & accounts → TikTok in its settings, "
              "then ask again.")


def comments_update(handle: str, read: list[dict]) -> str:
    """The update the Lace reads: each video and its comments."""
    total = sum(len(v["comments"]) for v in read)
    if total == 0:
        return f"Read @{handle}'s recent TikTok videos: no comments to read yet."
    lines = [f"Comments on @{handle}'s recent TikTok videos ({plural(total, 'comment')}). Point out the people "
             "worth reaching (buyers, partners, questions); replies can't be posted for the founder, so draft any "
             "for them to paste into TikTok:"]
    for video in read:
        caption = f" ({video['caption'][:80]})" if video["caption"] else ""
        lines.append(f"- {video['url']}{caption}")
        lines += [f"  - @{c['author'] or 'someone'}: {c['text']}" for c in video["comments"]]
    return "\n".join(lines)


async def tiktok_comments_job(run_id: uuid.UUID, lace_id: uuid.UUID, params: dict) -> None:
    """Read the comments on the founder's newest TikTok videos that have any."""
    apps = DbLaceApps(AsyncSessionLocal, lace_id)
    try:
        handle = await apps.handle("tiktok")
        if handle is None:
            raise JobBlocked(_NO_HANDLE)
        await events.publish(run_id, "step", {"text": f"Reading @{handle}'s videos"})
        videos = await asyncio.to_thread(tiktok.recent_videos, handle, settings, settings.social_read_timeout_s)
        chosen = [v for v in videos if (v["comments"] or 0) > 0][:params.get("videos", 3)]
        read = []
        for index, video in enumerate(chosen, 1):
            await events.publish(run_id, "step", {"text": f"Reading comments on video {index} of {len(chosen)}"})
            comments = await asyncio.to_thread(tiktok.video_comments, video["url"], settings,
                                               settings.tiktok_comments_timeout_s)
            read.append({"url": video["url"], "caption": video["text"], "comments": comments[:COMMENTS_PER_VIDEO]})
    except Exception as exc:
        await report_failure(lace_id, "TikTok comment read", exc)
        raise
    total = sum(len(v["comments"]) for v in read)
    async with AsyncSessionLocal() as db, db.begin():
        await lace_events.add(db, lace_id, comments_update(handle, read))
        await lace_activity.add(db, lace_id, "comments_read", f"Read {plural(total, 'TikTok comment')}",
                                f"On {plural(len(read), 'video')} of @{handle}" if read else "No comments yet")
    await set_run_fields(models.Run, run_id, status="completed", finished_at=datetime.now(UTC),
                         progress={"videos": len(read), "comments": total})
    await events.publish(run_id, "complete", {"comments": total})
