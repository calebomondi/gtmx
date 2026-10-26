"""backfill_lace_owners

Every existing Lace gets its creator as its active owner, keeping whether
they pinned it. Idempotent: a Lace that already has its owner is skipped.
The downgrade removes nothing, since the next one down drops the table.

Revision ID: 8b0d5c3e9a61
Revises: f4a72ea18f12
Create Date: 2026-10-24 18:44:00
"""

from alembic import op

revision = "8b0d5c3e9a61"
down_revision = "f4a72ea18f12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO lace_members (id, lace_id, user_id, role, status, pinned, created_at, responded_at)
        SELECT gen_random_uuid(), l.id, l.user_id, 'owner', 'active', l.pinned, l.created_at, l.created_at
        FROM laces l
        WHERE NOT EXISTS (SELECT 1 FROM lace_members m WHERE m.lace_id = l.id AND m.user_id = l.user_id)
    """)


def downgrade() -> None:
    pass
