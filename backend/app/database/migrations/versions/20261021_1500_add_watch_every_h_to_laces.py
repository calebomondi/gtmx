"""add_watch_every_h_to_laces

How often each Lace looks for new opportunities and competitor moves, in
hours, set by the founder. Existing Laces start at the default (6).

Revision ID: ce45f1924062
Revises: 171629245c56
Create Date: 2026-10-21 15:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "ce45f1924062"
down_revision = "171629245c56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("laces", sa.Column("watch_every_h", sa.SmallInteger(), server_default="6", nullable=False))
    op.create_check_constraint(op.f("ck_laces_watch_every_h"), "laces", "watch_every_h IN (6, 12, 24, 168)")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_laces_watch_every_h"), "laces", type_="check")
    op.drop_column("laces", "watch_every_h")
