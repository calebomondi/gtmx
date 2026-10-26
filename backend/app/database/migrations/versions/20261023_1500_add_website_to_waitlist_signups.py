"""add_website_to_waitlist_signups

The startup's website, asked in the waitlist's optional step, so the founder's
Lace can be set up from it when they're let in. Nullable: earlier signups
never gave one.

Revision ID: cba37e5de8cc
Revises: 2525c2f736b2
Create Date: 2026-10-23 15:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "cba37e5de8cc"
down_revision = "2525c2f736b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("waitlist_signups", sa.Column("website", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("waitlist_signups", "website")
