"""backfill_lace_domains

Each existing Lace's domain, read from its website as competitors.domain_key
does: the host, lowercased, without a port, userinfo, "www." or a trailing
dot. Where Laces share a domain, the oldest keeps it and the others stay NULL,
for an admin to merge or delete (admin Lace rows flag them). Idempotent.

Revision ID: a7c3e1f05d82
Revises: 5e2a9d4c7b13
Create Date: 2026-10-24 19:27:00
"""

from alembic import op

revision = "a7c3e1f05d82"
down_revision = "5e2a9d4c7b13"
branch_labels = None
depends_on = None

_HOST = ("rtrim(regexp_replace(split_part(regexp_replace(split_part(regexp_replace(lower(trim(website)), "
         "'^[a-z][a-z0-9+.-]*://', ''), '/', 1), '^.*@', ''), ':', 1), '^www\\.', ''), '.')")


def upgrade() -> None:
    op.execute(f"""
        UPDATE laces SET domain = firsts.domain
        FROM (
            SELECT DISTINCT ON (domain) id, domain FROM (SELECT id, created_at, {_HOST} AS domain FROM laces) hosts
            WHERE domain <> '' ORDER BY domain, created_at, id
        ) firsts
        WHERE laces.id = firsts.id AND laces.domain IS NULL
          AND NOT EXISTS (SELECT 1 FROM laces taken WHERE taken.domain = firsts.domain)
    """)


def downgrade() -> None:
    pass
