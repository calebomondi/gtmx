"""add_owner_to_lace_finds

A Lace's competitors, accounts and opportunities gain owner_id: NULL for the
team's (every existing row), or the member whose private chat found it
(no FK: Supabase owns users). Their keys become unique per owner, NULL
counting as one owner (NULLS NOT DISTINCT, Postgres 15+).

Downgrade deletes the private finds: the per-Lace uniqueness it restores
cannot hold with them.

Revision ID: 8b4d2f6e1a93
Revises: 5e8a1b3c7d20
Create Date: 2026-10-26 14:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "8b4d2f6e1a93"
down_revision = "5e8a1b3c7d20"
branch_labels = None
depends_on = None

# table, key column, old constraint name, new constraint name
_FINDS = (
    ("lace_competitors", "domain_key", "uq_lace_competitors_lace_id_domain_key",
     "uq_lace_competitors_lace_id_owner_id_domain_key"),
    ("lace_accounts", "key", "uq_lace_accounts_lace_id_key", "uq_lace_accounts_lace_id_owner_id_key"),
    ("lace_opportunities", "url_key", "uq_lace_opportunities_lace_id_url_key",
     "uq_lace_opportunities_lace_id_owner_id_url_key"),
)


def upgrade() -> None:
    for table, key, old, new in _FINDS:
        op.add_column(table, sa.Column("owner_id", sa.UUID(), nullable=True))
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {new} UNIQUE NULLS NOT DISTINCT (lace_id, owner_id, {key})")
        op.drop_constraint(old, table, type_="unique")


def downgrade() -> None:
    for table, key, old, new in _FINDS:
        op.execute(f"DELETE FROM {table} WHERE owner_id IS NOT NULL")
        op.create_unique_constraint(old, table, ["lace_id", key])
        op.drop_constraint(new, table, type_="unique")
        op.drop_column(table, "owner_id")
