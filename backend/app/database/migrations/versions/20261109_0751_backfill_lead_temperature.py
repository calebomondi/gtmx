"""backfill_lead_temperature

Data migration: leads whose replies already show interest start warm, and those
who asked for a meeting start hot, each with the reply as its reason and its
signal. Same rules as the code that sets temperature from now on
(backend/app/services/lead_temperature.py).

Idempotent: it only touches leads whose temperature was never set
(temperature_changed_at IS NULL), and adds a signal only for a reply that has
none yet. The downgrade puts those leads back to cold and removes the signals
it added.

Revision ID: 5f1c2a9d8e47
Revises: e33fc680e1ad
Create Date: 2026-11-09 07:51:00+00:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = '5f1c2a9d8e47'
down_revision: Union[str, Sequence[str], None] = 'e33fc680e1ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The reason each reply intent gives, and the temperature it means. Mirrors
# lead_temperature.REPLY_SIGNALS as of this migration; kept inline so the
# migration does not change when that code does.
_REASON = """CASE r.intent
    WHEN 'meeting_request' THEN 'Asked for a meeting'
    WHEN 'interested' THEN 'Replied with interest'
    WHEN 'question' THEN 'Replied with a question'
    WHEN 'objection' THEN 'Replied with an objection'
    WHEN 'referral' THEN 'Pointed you to someone else'
END"""
_TEMPERATURE = "CASE WHEN r.intent = 'meeting_request' THEN 'hot' ELSE 'warm' END"
_RANK = "CASE WHEN r.intent = 'meeting_request' THEN 2 ELSE 1 END"
_BACKFILLED = "'(from earlier replies)'"


def upgrade() -> None:
    # Each lead's strongest reply: a meeting request beats interest, and the
    # latest reply wins a tie.
    op.execute(f"""
        WITH best AS (
            SELECT DISTINCT ON (r.account_id)
                   r.account_id, r.lace_id, r.id AS outreach_id, r.created_at AS at,
                   {_REASON} AS reason, {_TEMPERATURE} AS temperature
            FROM lace_outreach r
            JOIN lace_accounts a ON a.id = r.account_id
            WHERE r.direction = 'inbound' AND r.account_id IS NOT NULL
              AND r.intent IN ('meeting_request', 'interested', 'question', 'objection', 'referral')
              AND a.temperature_changed_at IS NULL
            ORDER BY r.account_id, {_RANK} DESC, r.created_at DESC
        ),
        signals AS (
            INSERT INTO lace_account_signals (id, lace_id, account_id, kind, detail, outreach_id, before, after, at)
            SELECT gen_random_uuid(), b.lace_id, b.account_id, 'reply', b.reason || ' ' || {_BACKFILLED},
                   b.outreach_id, 'cold', b.temperature, b.at
            FROM best b
            WHERE NOT EXISTS (SELECT 1 FROM lace_account_signals s WHERE s.outreach_id = b.outreach_id)
            RETURNING account_id
        )
        UPDATE lace_accounts a
        SET temperature = b.temperature, temperature_reason = b.reason, temperature_changed_at = b.at
        FROM best b
        WHERE a.id = b.account_id
    """)


def downgrade() -> None:
    op.execute(f"""
        UPDATE lace_accounts a
        SET temperature = 'cold', temperature_reason = NULL, temperature_changed_at = NULL
        WHERE EXISTS (SELECT 1 FROM lace_account_signals s
                      WHERE s.account_id = a.id AND s.detail LIKE '%' || {_BACKFILLED})
    """)
    op.execute(f"DELETE FROM lace_account_signals WHERE detail LIKE '%' || {_BACKFILLED}")
