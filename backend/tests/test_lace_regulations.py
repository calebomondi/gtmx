"""Regulations and the startup's jurisdictions: the database keeps codes,
kinds and bill stages to their known values, and one row per source page."""

import uuid

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from backend.app.database.connect import AsyncSessionLocal
from backend.app.database.lace_models import Lace, LaceRegulation
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import lace_runtime  # noqa: F401 -- fixture

VAT_BILL = {"kind": "bill", "title": "The Value Added Tax (Amendment) Bill, 2026", "jurisdiction": "KE",
            "url": "https://kenyalaw.org/akn/ke/bill/na/2026-04-10/vat-amendment-bill-2026",
            "url_key": "kenyalaw.org/akn/ke/bill/na/2026-04-10/vat-amendment-bill-2026", "stage": "first_reading"}


async def _add(lace_id: str, fields: dict | None = None) -> None:
    async with AsyncSessionLocal() as db:
        db.add(LaceRegulation(lace_id=uuid.UUID(lace_id), **{**VAT_BILL, **(fields or {})}))
        await db.commit()


async def _place(lace_id: str, registered_in: str | None, operates_in: list[str]) -> Lace:
    async with AsyncSessionLocal() as db:
        await db.execute(update(Lace).where(Lace.id == uuid.UUID(lace_id))
                         .values(registered_in=registered_in, operates_in=operates_in))
        await db.commit()
        return await db.get(Lace, uuid.UUID(lace_id))


def test_a_lace_starts_with_no_jurisdiction(client, lace):  # noqa: F811
    placed = client.portal.call(_place, lace, None, [])
    assert placed.registered_in is None and placed.operates_in == [] and placed.jurisdiction_confirmed_at is None


@pytest.mark.parametrize("code", ["KE", "US-DE", "GB-SCT"])
def test_iso_codes_are_kept(client, lace, code):  # noqa: F811
    placed = client.portal.call(_place, lace, code, ["KE", "NG"])
    assert placed.registered_in == code and placed.operates_in == ["KE", "NG"]


@pytest.mark.parametrize("code", ["Kenya", "ke", "K", "KE-"])
def test_anything_but_an_iso_code_is_refused(client, lace, code):  # noqa: F811
    with pytest.raises(IntegrityError):
        client.portal.call(_place, lace, code, [])
    with pytest.raises(IntegrityError):
        client.portal.call(_add, lace, {"jurisdiction": code})


def test_a_new_regulation_waits_for_the_founder(client, lace):  # noqa: F811
    client.portal.call(_add, lace)

    async def read():
        async with AsyncSessionLocal() as db:
            return (await db.execute(LaceRegulation.__table__.select())).one()
    row = client.portal.call(read)
    assert row.status == "suggested" and row.last_checked_at is None and row.owner_id is None


@pytest.mark.parametrize("field", [{"kind": "rule"}, {"stage": "debated"}, {"status": "open"}])
def test_unknown_kinds_stages_and_statuses_are_refused(client, lace, field):  # noqa: F811
    with pytest.raises(IntegrityError):
        client.portal.call(_add, lace, field)


def test_one_row_per_source_page(client, lace):  # noqa: F811
    client.portal.call(_add, lace)
    with pytest.raises(IntegrityError):
        client.portal.call(_add, lace, {"title": "The VAT (Amendment) Bill, 2026"})
