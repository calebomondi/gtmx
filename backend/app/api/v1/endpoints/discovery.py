"""Discovery over a WebSocket that only SUBSCRIBES to a server-owned run.

First client message, one of:
  - a DiscoveryRequest             -> start a new run
  - {"resume": run_id, "after": N} -> reattach, replaying events after id N
Then the server streams the run's frames (each carries `run_id` and
`event_id`), and the client sends {"answer": "..."} when asked a question.
Disconnecting ends the subscription, never the run.
"""

import asyncio
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from backend.app.api.deps import websocket_user
from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs import events, manager
from backend.app.schemas.agents import DiscoveryRequest
from backend.app.services import runs as run_service
from backend.app.services.errors import ServiceError
from utils.log import logger

router = APIRouter()


async def _open_run(websocket: WebSocket, user_id: uuid.UUID) -> tuple[uuid.UUID, int] | None:
    """Start or reattach per the first message. None after sending an error."""
    try:
        message = json.loads(await websocket.receive_text())
        if isinstance(message, dict) and "resume" in message:
            run_id = uuid.UUID(str(message["resume"]))
            async with AsyncSessionLocal() as db:
                await run_service.get_owned(db, user_id, run_id)
            return run_id, int(message.get("after") or 0)
        run = await manager.start_discovery(user_id, DiscoveryRequest.model_validate(message))
        return run.id, 0
    except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
        await websocket.send_json({"type": "error", "message": f"Invalid request: {exc}"})
    except ServiceError as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
    await websocket.close(code=1008)
    return None


async def _relay_answers(websocket: WebSocket, user_id: uuid.UUID, run_id: uuid.UUID) -> None:
    while True:
        text = await websocket.receive_text()
        try:
            data = json.loads(text)
            answer = data.get("answer") if isinstance(data, dict) else None
        except json.JSONDecodeError:
            answer = text
        try:
            await manager.answer(user_id, run_id, answer or "")
        except ServiceError as exc:
            await websocket.send_json({"type": "notice", "run_id": str(run_id), "message": str(exc)})


async def _stream_events(websocket: WebSocket, run_id: uuid.UUID, after_id: int) -> None:
    async for frame in events.subscribe(run_id, after_id):
        await websocket.send_json(frame)
        if frame["type"] in events.TERMINAL_FRAME_TYPES:
            return


@router.websocket("")
async def discovery_socket(websocket: WebSocket):
    await websocket.accept()
    user = await websocket_user(websocket)
    if user is None:
        await websocket.send_json({"type": "error", "message": "Authentication required"})
        await websocket.close(code=4401)
        return

    try:
        opened = await _open_run(websocket, user.id)
        if opened is None:
            return
        run_id, after_id = opened
        await websocket.send_json({"type": "run", "run_id": str(run_id), "session_id": str(run_id)})

        stream = asyncio.create_task(_stream_events(websocket, run_id, after_id))
        answers = asyncio.create_task(_relay_answers(websocket, user.id, run_id))
        done, pending = await asyncio.wait({stream, answers}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            exc = task.exception()
            if exc is not None and not isinstance(exc, WebSocketDisconnect):
                raise exc
        if stream in done:
            await websocket.close(code=1000)
    except WebSocketDisconnect:
        return  # the run carries on; the client can reattach
    except Exception:
        logger.exception("Discovery socket failed")
        try:
            await websocket.close(code=1011)
        except RuntimeError:
            pass
