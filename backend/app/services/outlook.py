"""Email through a founder's Outlook (Microsoft 365 or Outlook.com), via
Composio: sending, replying in a conversation, and recent mail for the reply
sync. Tools and their argument names verified against the live Composio
catalog (2026-10-24). Synchronous: call these in a worker thread.

Outlook's send answers with no message id, so a new email is found again in
Sent Items (by subject and recipient) for its conversation id, which replies
are matched on. Recent mail comes back in the shape the reply sync reads
(Gmail's keys), so one sync serves both."""

import html
import re

from backend.app.services import connections as connection_service
from backend.app.services.connections import ConnectionInfo
from utils.log import logger

_SEND = "OUTLOOK_OUTLOOK_SEND_EMAIL"
_REPLY = "OUTLOOK_OUTLOOK_REPLY_EMAIL"
_LIST = "OUTLOOK_OUTLOOK_LIST_MESSAGES"
# Sent emails looked through to find the one just sent; recent inbox mail per sync.
SENT_LOOKUP = 5
RECENT = 50
_TAG = re.compile(r"<[^>]+>")
_BLANK_LINES = re.compile(r"\n\s*\n+")


def _graph(data) -> dict:
    """The Microsoft Graph response inside Composio's wrapper."""
    inner = data.get("response_data") if isinstance(data, dict) else None
    return inner if isinstance(inner, dict) else {}


def _messages(data) -> list[dict]:
    return [m for m in _graph(data).get("value") or [] if isinstance(m, dict)]


def send(account: ConnectionInfo, to: str, subject: str, body: str) -> dict:
    """Send a new email. Returns {error, log_id, message_id, thread_id}; the
    ids are None when the sent email couldn't be found again."""
    result = connection_service.execute_tool(account.entity, _SEND, {
        "to_email": to, "subject": subject, "body": body, "is_html": False, "save_to_sent_items": True,
    }, account.id)
    sent = None if result.get("error") else _find_sent(account, to, subject)
    return {"error": result.get("error"), "log_id": result.get("log_id"),
            "message_id": sent.get("id") if sent else None, "thread_id": sent.get("conversationId") if sent else None}


def reply(account: ConnectionInfo, message_id: str, body: str) -> dict:
    """Answer a message, in its conversation. Returns {error, log_id}."""
    result = connection_service.execute_tool(account.entity, _REPLY, {"message_id": message_id, "comment": body},
                                             account.id)
    return {"error": result.get("error"), "log_id": result.get("log_id")}


def _find_sent(account: ConnectionInfo, to: str, subject: str) -> dict | None:
    result = connection_service.execute_tool(account.entity, _LIST, {
        "folder": "SentItems", "subject": subject, "top": SENT_LOOKUP, "orderby": ["sentDateTime desc"],
        "select": ["id", "conversationId", "toRecipients"],
    }, account.id)
    if result.get("error"):
        logger.info("Finding the sent Outlook email to %s failed: %s", to, result["error"])
        return None
    for message in _messages(result.get("data")):
        recipients = {((r.get("emailAddress") or {}).get("address") or "").lower()
                      for r in message.get("toRecipients") or [] if isinstance(r, dict)}
        if to.lower() in recipients:
            return message
    return None


def _text(message: dict) -> str:
    """The message's own words (Outlook's uniqueBody leaves out the quoted
    mail), as plain text."""
    body = message.get("uniqueBody") or message.get("body") or {}
    content = body.get("content") if isinstance(body, dict) else None
    if not content:
        return message.get("bodyPreview") or ""
    if (body.get("contentType") or "").lower() == "html":
        content = _TAG.sub("\n", re.sub(r"(?is)<(style|script)[^>]*>.*?</\1>", "", content))
    return _BLANK_LINES.sub("\n\n", html.unescape(content)).strip()


def recent(account: ConnectionInfo, since_iso: str) -> list[dict]:
    """Inbox mail received since `since_iso`, newest first, bounded, with
    Gmail's keys: messageId, threadId, sender, subject, messageText,
    messageTimestamp."""
    result = connection_service.execute_tool(account.entity, _LIST, {
        "folder": "Inbox", "received_date_time_ge": since_iso, "top": RECENT, "orderby": ["receivedDateTime desc"],
        "select": ["id", "conversationId", "from", "subject", "uniqueBody", "bodyPreview", "receivedDateTime"],
    }, account.id)
    if result.get("error"):
        logger.info("Outlook fetch for %s failed: %s", account.entity, result["error"])
        return []
    found = []
    for message in _messages(result.get("data")):
        sender = (message.get("from") or {}).get("emailAddress") or {}
        name, address = sender.get("name") or "", sender.get("address") or ""
        found.append({
            "messageId": message.get("id"), "threadId": message.get("conversationId"),
            "sender": f"{name} <{address}>" if name else address, "subject": message.get("subject"),
            "messageText": _text(message), "messageTimestamp": message.get("receivedDateTime"),
        })
    return found
