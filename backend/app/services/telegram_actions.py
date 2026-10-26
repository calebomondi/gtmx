"""The Telegram actions a Lace can propose (or the founder set up, like the
brief), run through the founder's bot (lace_app_actions): a message to a
channel, group or chat. Composio tool verified against the live catalog
(2026-10-25)."""

from backend.app.services.lace_app_actions import Outcome, RunContext, call, runs


def _link(chat_id: str, message_id) -> str | None:
    """A public channel's post link; private chats and groups have none."""
    return f"https://t.me/{chat_id[1:]}/{message_id}" if chat_id.startswith("@") and message_id else None


@runs("telegram", "send_message")
async def send_message(ctx: RunContext, arguments: dict) -> Outcome:
    done = await call(ctx, "TELEGRAM_SEND_MESSAGE", {"chat_id": arguments["chat_id"], "text": arguments["text"],
                                                     "disable_web_page_preview": True})
    data = done["data"] if isinstance(done["data"], dict) else {}
    message_id = (data.get("result") or data).get("message_id")
    return Outcome(f"Sent to {arguments['chat_id']} on Telegram.", _link(arguments["chat_id"], message_id),
                   done["log_id"])
