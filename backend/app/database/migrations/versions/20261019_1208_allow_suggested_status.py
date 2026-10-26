"""allow suggested status

Competitors, target accounts and opportunities a search finds now start as
'suggested' and are worked from only once the founder saves them (tracked,
target, open). Existing rows keep their status, so everything already on
file counts as saved. Only the CHECK constraints change.

Revision ID: 83be1868cf57
Revises: d2e547478305
Create Date: 2026-10-19 12:08:38+00:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = '83be1868cf57'
down_revision: Union[str, Sequence[str], None] = 'd2e547478305'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# table: (saved status, the statuses before this migration)
_TABLES = {
    'lace_competitors': ('tracked', ('tracked', 'dismissed')),
    'lace_accounts': ('target', ('target', 'dismissed')),
    'lace_opportunities': ('open', ('open', 'dismissed')),
}


def _check(table: str, statuses: tuple[str, ...]) -> None:
    op.drop_constraint(op.f(f'ck_{table}_status'), table, type_='check')
    op.create_check_constraint(op.f(f'ck_{table}_status'), table,
                               "status IN (" + ", ".join(repr(s) for s in statuses) + ")")


def upgrade() -> None:
    for table, (_, before) in _TABLES.items():
        _check(table, ('suggested', *before))


def downgrade() -> None:
    # Without the status, a suggestion can only become what it would have
    # been before: saved.
    for table, (saved, before) in _TABLES.items():
        op.execute(f"UPDATE {table} SET status = '{saved}' WHERE status = 'suggested'")
        _check(table, before)
