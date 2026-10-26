"""strip_quotes_from_email_replies

Email replies were stored with the mail they answer quoted below them. Keep
only the reply's own words. Data only, and idempotent: a stripped reply has no
quote left to strip. The rule is a frozen copy of
backend.app.services.inbox.reply_only, so this migration never changes with it.
Downgrade keeps the stripped text (the quotes are the founder's own sent mail,
already stored on the outbound row).

Revision ID: c427154b4559
Revises: af632637180b
Create Date: 2026-10-22 12:00:00
"""

import re

import sqlalchemy as sa
from alembic import op

revision = "c427154b4559"
down_revision = "af632637180b"
branch_labels = None
depends_on = None

_QUOTE_STARTS = (
    re.compile(r"^[ \t]*On\b[^\n]{0,300}(?:\n[^\n]{0,300})?\bwrote:[ \t]*$", re.M),
    re.compile(r"^[ \t]*-{2,}[ \t]*Original Message[ \t]*-{2,}", re.M | re.I),
    re.compile(r"^[ \t]*From:[^\n]*\n[ \t]*(?:Sent|Date):", re.M),
    re.compile(r"^[ \t]*>", re.M),
)


def _reply_only(text: str) -> str:
    cut = min((m.start() for pattern in _QUOTE_STARTS if (m := pattern.search(text))), default=len(text))
    return text[:cut].rstrip() or text.strip()


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id, body FROM lace_outreach WHERE channel = 'email' AND direction = 'inbound'")).all()
    for row_id, body in rows:
        stripped = _reply_only(body or "")
        if stripped != body:
            conn.execute(sa.text("UPDATE lace_outreach SET body = :body WHERE id = :id"), {"body": stripped, "id": row_id})


def downgrade() -> None:
    pass
