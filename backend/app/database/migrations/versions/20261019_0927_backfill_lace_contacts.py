"""backfill lace contacts

Data migration: copies the people already in each account record's
key_contacts into lace_contacts, so Contacts shows everyone found before the
table existed. The key and the stored fields mirror
backend.app.services.lace_contacts (contact_key, sync). When two accounts name
the same person, the account seen most recently wins. Idempotent: a person
already on file is left as it is.

Revision ID: d2e547478305
Revises: ffc4d9799974
Create Date: 2026-10-19 09:27:00+00:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd2e547478305'
down_revision: Union[str, Sequence[str], None] = 'ffc4d9799974'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BACKFILL_SQL = """
WITH people AS (
    SELECT a.lace_id, a.id AS account_id, a.last_seen_at,
           CASE WHEN a.contacts_checked_at IS NULL THEN 'discovery' ELSE 'contact_search' END AS source,
           nullif(btrim(c->>'name'), '') AS name,
           nullif(btrim(c->>'title'), '') AS title,
           nullif(btrim(c->>'email'), '') AS email,
           nullif(btrim(c->>'linkedin'), '') AS linkedin
    FROM lace_accounts a
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE WHEN jsonb_typeof(a.record->'key_contacts') = 'array' THEN a.record->'key_contacts' ELSE '[]'::jsonb END
    ) AS c
), keyed AS (
    SELECT *, left(lower(coalesce(email, nullif(rtrim(linkedin, '/'), ''), name)), 320) AS key
    FROM people
)
INSERT INTO lace_contacts (id, lace_id, account_id, key, name, title, email, linkedin, source,
                           first_seen_at, last_seen_at)
SELECT DISTINCT ON (lace_id, key)
       gen_random_uuid(), lace_id, account_id, key, left(name, 200), left(title, 200), left(email, 320), linkedin,
       source, now(), now()
FROM keyed
WHERE key IS NOT NULL
ORDER BY lace_id, key, last_seen_at DESC
ON CONFLICT (lace_id, key) DO NOTHING
"""


def upgrade() -> None:
    op.execute(BACKFILL_SQL)


def downgrade() -> None:
    # Nothing to undo: the rows are a copy of what the account records still
    # hold, and the ones synced since cannot be told apart from them.
    pass
