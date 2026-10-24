"""What a Lace proposes doing in its founder's apps, and running it on their
click.

A Lace never acts in an app by itself: its tools store a proposal (a post, a
reply to a comment, a lead), shown under its reply with Approve and Decline.
Approving runs the action through Composio as the founder, records the
outcome, puts it on the Feed and tells the Lace; declining tells the Lace too.

Each runnable action is registered with `runs(app, action)`: a function that
gets the founder's id, their live connection to the app, and the proposal's
arguments, runs synchronously (in a worker thread), and returns an Outcome or
raises ActionFailed with a reason the founder can read.
"""

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas.lace import AppActionStatus, ProposedAction
from backend.app.database.lace_models import LaceAppAction
from backend.app.services import connections as connection_service
from backend.app.services import lace_activity, lace_events
from backend.app.services.errors import ConflictError, NotFoundError
from utils.log import logger


@dataclass(frozen=True)
class Outcome:
    """What running an action produced: a line for the founder and the Lace,
    a link to the result when there is one, and Composio's log id."""
    result: str
    url: str | None = None
    log_id: str | None = None


class ActionFailed(Exception):
    """The app refused the action. The message is said to the founder as is."""


Runner = Callable[[uuid.UUID, str, dict], Outcome]
RUNNERS: dict[tuple[str, str], Runner] = {}


def runs(app: str, action: str) -> Callable[[Runner], Runner]:
    """Register the function that runs `action` in `app`."""
    def register(fn: Runner) -> Runner:
        RUNNERS[(app, action)] = fn
        return fn
    return register


async def propose(db: AsyncSession, lace_id: uuid.UUID, proposal: ProposedAction) -> LaceAppAction:
    row = LaceAppAction(lace_id=lace_id, app=proposal.app, action=proposal.action, title=proposal.title,
                        preview=proposal.preview, arguments=proposal.arguments)
    db.add(row)
    await db.commit()
    return row


async def get_in_lace(db: AsyncSession, lace_id: uuid.UUID, action_id: uuid.UUID) -> LaceAppAction:
    """404 for an action that is not this Lace's."""
    row = await db.scalar(select(LaceAppAction).where(LaceAppAction.id == action_id, LaceAppAction.lace_id == lace_id))
    if row is None:
        raise NotFoundError("Action not found")
    return row


async def list_for_lace(db: AsyncSession, lace_id: uuid.UUID, limit: int,
                        status: AppActionStatus | None = None) -> list[LaceAppAction]:
    """Newest first."""
    query = select(LaceAppAction).where(LaceAppAction.lace_id == lace_id)
    if status:
        query = query.where(LaceAppAction.status == status)
    return list((await db.scalars(query.order_by(LaceAppAction.created_at.desc()).limit(limit))).all())


def _waiting(row: LaceAppAction) -> None:
    if row.status != "proposed":
        raise ConflictError(f"This was already {'approved' if row.status in ('running', 'done', 'failed') else row.status}.")


async def approve(db: AsyncSession, row: LaceAppAction, user_id: uuid.UUID) -> LaceAppAction:
    """Run the action as the founder. The founder must have the app connected;
    otherwise it stays proposed and they're told to connect it."""
    _waiting(row)
    runner = RUNNERS.get((row.app, row.action))
    if runner is None:
        raise ConflictError("Your Lace can't do that yet.")
    connection = next((c for c in await connection_service.list_for_user(db, user_id)
                       if c.platform == row.app and c.status == "live"), None)
    if connection is None:
        raise ConflictError(f"Connect your {connection_service.label(row.app)} account first (Accounts page).")

    # Claimed before the app is called, so a double click can't run it twice.
    row.status, row.decided_at = "running", datetime.now(UTC)
    await db.commit()
    try:
        outcome = await asyncio.to_thread(runner, user_id, connection.id, row.arguments)
        row.status, row.result, row.url, row.provider_log_id = "done", outcome.result, outcome.url, outcome.log_id
    except ActionFailed as exc:
        row.status, row.result = "failed", str(exc)
    except Exception:  # noqa: BLE001 -- an expected outcome: recorded on the action
        logger.exception("App action %s (%s %s) failed", row.id, row.app, row.action)
        row.status, row.result = "failed", f"Couldn't reach {connection_service.label(row.app)}. Please try again."
    row.finished_at = datetime.now(UTC)
    done = row.status == "done"
    await lace_activity.add(db, row.lace_id, "app_action", f"{row.title}: {'done' if done else 'didn’t go through'}",
                            row.result, ref=("app_action", row.id))
    await lace_events.add(db, row.lace_id, f"The founder approved \"{row.title}\" and it "
                          + (f"ran: {row.result}" if done else f"failed: {row.result}"))
    await db.commit()
    await db.refresh(row)
    return row


async def decline(db: AsyncSession, row: LaceAppAction) -> LaceAppAction:
    _waiting(row)
    row.status, row.decided_at = "declined", datetime.now(UTC)
    await lace_events.add(db, row.lace_id, f"The founder declined \"{row.title}\": it was not run.")
    await db.commit()
    await db.refresh(row)
    return row


async def statuses(db: AsyncSession, lace_id: uuid.UUID, ids: set[uuid.UUID]) -> dict[str, LaceAppAction]:
    """These actions as they stand now, by id, for the cards under replies."""
    rows = await db.scalars(select(LaceAppAction).where(LaceAppAction.lace_id == lace_id, LaceAppAction.id.in_(ids)))
    return {str(row.id): row for row in rows}
