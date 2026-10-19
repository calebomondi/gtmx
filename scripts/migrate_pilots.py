"""Move v1 pilot workspaces into Laces (backend.app.services.pilot_migration).

A dry run by default: it prints what each workspace would become and writes
nothing. Read the report, then run again with --apply. Safe to re-run: what
was already moved is not moved twice.

    uv run python -m scripts.migrate_pilots                  # report only
    uv run python -m scripts.migrate_pilots --user-id <uuid> # one founder
    uv run python -m scripts.migrate_pilots --apply          # write

Runs against the database in DATABASE_URL: check it is the one you mean.
"""

import argparse
import asyncio
import uuid

from psycopg.conninfo import conninfo_to_dict

from backend.app.database.connect import AsyncSessionLocal, engine
from backend.app.services import pilot_migration
from config import settings


def _where() -> str:
    parts = conninfo_to_dict(settings.database_url)
    return f"{parts.get('host', 'localhost')}:{parts.get('port', 5432)}/{parts.get('dbname', '?')}"


def _report(plan: pilot_migration.MigrationPlan) -> None:
    print(f"{len(plan.workspaces)} workspaces; {plan.laces} new Laces; {len(plan.skipped)} without a website (skipped)\n")
    for w in plan.workspaces:
        where = w.website or "NO WEBSITE: skipped"
        lace = "existing Lace" if w.lace_exists else "new Lace" if w.movable else "-"
        print(f"- {w.name} [{w.workspace_id}] user {w.user_id}\n    {where} -> {lace}: {w.facts} facts, "
              f"{w.competitors} competitors, {w.accounts} accounts, {w.contacts} contacts, {w.messages} messages"
              + (f"\n    {w.accounts_without_trigger} accounts without a trigger stay behind"
                 if w.accounts_without_trigger else ""))


async def main(apply: bool, user_id: uuid.UUID | None) -> None:
    print(f"Database: {_where()}\n")
    async with AsyncSessionLocal() as db:
        _report(await pilot_migration.plan(db, user_id))
    if apply:
        laces = await pilot_migration.apply(AsyncSessionLocal, user_id)
        print(f"\nMoved into {len(laces)} Laces.")
    else:
        print("\nDry run: nothing was written. Run with --apply to move them.")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write; without it, only report")
    parser.add_argument("--user-id", type=uuid.UUID, help="only this founder's workspaces")
    args = parser.parse_args()
    asyncio.run(main(args.apply, args.user_id))
