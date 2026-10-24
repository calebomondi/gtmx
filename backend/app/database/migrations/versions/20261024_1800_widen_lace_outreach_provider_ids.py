"""widen_lace_outreach_provider_ids

Outlook's message and conversation ids run to about 150 characters, past the
64 (thread) and 128 (message) that fit Gmail's. Widening a varchar only
rewrites the column's limit; the downgrade cuts longer ids back to fit.

Revision ID: 3f1c9a7e2b54
Revises: 761ed96052bd
Create Date: 2026-10-24 18:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "3f1c9a7e2b54"
down_revision = "761ed96052bd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("lace_outreach", "thread_id", type_=sa.String(length=255), existing_type=sa.String(length=64),
                    existing_nullable=True)
    op.alter_column("lace_outreach", "provider_message_id", type_=sa.String(length=255),
                    existing_type=sa.String(length=128), existing_nullable=True)


def downgrade() -> None:
    op.alter_column("lace_outreach", "provider_message_id", type_=sa.String(length=128),
                    existing_type=sa.String(length=255), existing_nullable=True,
                    postgresql_using="left(provider_message_id, 128)")
    op.alter_column("lace_outreach", "thread_id", type_=sa.String(length=64), existing_type=sa.String(length=255),
                    existing_nullable=True, postgresql_using="left(thread_id, 64)")
