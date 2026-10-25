"""add_telegram_inbox

Telegram as an inbox a Lace can be linked to (its founder's bot) and as an
outreach channel for the conversations it brings, plus where each linked
bot's update read last stopped.

Revision ID: 9d2f6a1c3e47
Revises: c41b8e2d6f90
Create Date: 2026-10-25 15:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "9d2f6a1c3e47"
down_revision = "c41b8e2d6f90"
branch_labels = None
depends_on = None

_CHANNELS = "'email', 'linkedin', 'x', 'instagram', 'facebook', 'tiktok'"
_PLATFORMS = "'instagram', 'facebook'"


def _checks(channels: str, platforms: str) -> None:
    op.drop_constraint(op.f("ck_lace_outreach_channel"), "lace_outreach", type_="check")
    op.create_check_constraint(op.f("ck_lace_outreach_channel"), "lace_outreach", f"channel IN ({channels})")
    op.drop_constraint(op.f("ck_lace_channels_platform"), "lace_channels", type_="check")
    op.create_check_constraint(op.f("ck_lace_channels_platform"), "lace_channels", f"platform IN ({platforms})")


def upgrade() -> None:
    op.add_column("lace_channels", sa.Column("sync_cursor", sa.String(length=32), nullable=True))
    _checks(f"{_CHANNELS}, 'telegram'", f"{_PLATFORMS}, 'telegram'")


def downgrade() -> None:
    op.execute("DELETE FROM lace_outreach WHERE channel = 'telegram'")
    op.execute("DELETE FROM lace_channels WHERE platform = 'telegram'")
    _checks(_CHANNELS, _PLATFORMS)
    op.drop_column("lace_channels", "sync_cursor")
