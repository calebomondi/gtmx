"""allow_founder_contact_source

A contact can now be one the founder added through their Lace.

Revision ID: 171629245c56
Revises: c202a1ec964a
Create Date: 2026-10-21 13:00:00
"""

from alembic import op

revision = "171629245c56"
down_revision = "c202a1ec964a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_lace_contacts_source"), "lace_contacts", type_="check")
    op.create_check_constraint(op.f("ck_lace_contacts_source"), "lace_contacts",
                               "source IN ('discovery', 'contact_search', 'founder')")


def downgrade() -> None:
    # Founder-added people predate any search of theirs; count them as discovery.
    op.execute("UPDATE lace_contacts SET source = 'discovery' WHERE source = 'founder'")
    op.drop_constraint(op.f("ck_lace_contacts_source"), "lace_contacts", type_="check")
    op.create_check_constraint(op.f("ck_lace_contacts_source"), "lace_contacts",
                               "source IN ('discovery', 'contact_search')")
