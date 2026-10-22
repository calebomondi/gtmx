"""add_socials_to_lace_contacts

A person's own X, Instagram, Facebook and TikTok profiles, beside their email
and LinkedIn, so Contacts can offer every way to reach them. Nullable: nobody
on file has them yet.

Revision ID: af632637180b
Revises: ce45f1924062
Create Date: 2026-10-22 09:30:00
"""

import sqlalchemy as sa
from alembic import op

revision = "af632637180b"
down_revision = "ce45f1924062"
branch_labels = None
depends_on = None

_COLUMNS = ("x", "instagram", "facebook", "tiktok")


def upgrade() -> None:
    for column in _COLUMNS:
        op.add_column("lace_contacts", sa.Column(column, sa.Text(), nullable=True))


def downgrade() -> None:
    for column in reversed(_COLUMNS):
        op.drop_column("lace_contacts", column)
