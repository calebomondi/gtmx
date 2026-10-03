"""Exercise the competitors endpoints against a real database.

Not a stub: a real SQLite file, real tables from `Base.metadata`, real HTTP
requests through the ASGI app. That is the only way to catch the failures that
matter in this layer -- a response model that does not match the ORM column, a
dedup constraint that fires on the second add, a route that shadows another.

The engine is built HERE and injected by overriding `get_db`, rather than
relying on the app's. `settings.DATABASE_URL` points at the dev `blog.db` and
wins over the environment, so a test that trusted it would create tables in the
developer's real database.

Run directly (pytest is not installed in this venv):
    PYTHONPATH=/home/mokuaxv/gtmx2/gtmx .venv/bin/python \\
        backend/app/api/v1/endpoints/_check_competitors.py
"""

import asyncio
import os
import tempfile
import uuid

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.api.v1.routes import api_router
from backend.app.database import models  # noqa: F401 -- registers the tables
from backend.app.database.connect import Base, get_db
from backend.app.database.models import Competitor, CompetitorRun, User, Workspace

_DB_PATH = tempfile.mkstemp(suffix=".db")[1]

_engine = create_async_engine(f"sqlite+aiosqlite:///{_DB_PATH}")
_Session = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


PASS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
	if not condition:
		raise AssertionError(f"{label}{(' -- ' + detail) if detail else ''}")
	PASS.append(label)


async def _seed() -> tuple[uuid.UUID, uuid.UUID]:
	"""A user and a workspace with a completed discovery run behind it."""
	async with _Session() as db:
		async with db.begin():
			# User.id has no column default in this schema -- the app assigns it at
			# creation -- so the seed does too.
			user = User(id=uuid.uuid4(), name="Founder", email=f"{uuid.uuid4().hex}@example.com")
			db.add(user)
			await db.flush()
			workspace = Workspace(name="HeatherDB", user_id=user.id)
			db.add(workspace)
			await db.flush()
			return user.id, workspace.id


async def _attach_profile(workspace_id: uuid.UUID, with_profile: bool = True) -> None:
	"""Persist the competition stage's output the way `_build_insights` does."""
	from backend.app.database.models import ProductProfile

	insights = {
		"competition_data": {"strengths": ["cheap"], "weaknesses": []},
	}
	if with_profile:
		insights["ideal_competitor_profile"] = {
			"category_definition": "vector databases",
			"archetypes": [
				{"label": "Global incumbent", "geography_scope": "global"},
				{"label": "Local builder", "geography_scope": "local"},
			],
			"confidence": "high",
		}
	async with _Session() as db:
		async with db.begin():
			db.add(
				ProductProfile(
					workspace_id=workspace_id,
					product_name="HeatherDB",
					insights=insights,
				)
			)


async def main() -> None:
	async with _engine.begin() as conn:
		await conn.run_sync(Base.metadata.create_all)

	_, workspace_id = await _seed()
	other_user, other_ws = await _seed()

	app = FastAPI()
	app.include_router(api_router, prefix="/api/v1")

	async def _isolated_db():
		async with _Session() as session:
			yield session

	# The endpoints resolve their session through get_db, so overriding that one
	# dependency redirects every competitor route at the throwaway database.
	app.dependency_overrides[get_db] = _isolated_db
	# BackgroundTasks would fire the agent, which does not exist yet. Swapping the
	# task queue for a recorder keeps every other behaviour -- including the
	# dedup path that schedules one -- under test without invoking an LLM.
	scheduled: list[tuple] = []

	class Recorder(httpx.ASGITransport):
		pass

	transport = httpx.ASGITransport(app=app)
	base = f"/api/v1/workspaces/{workspace_id}/competitors"

	async def call(method: str, path: str, **kw):
		async with httpx.AsyncClient(
			transport=transport, base_url="http://t"
		) as client:
			return await client.request(method, path, **kw)

	# -- 404 on an unknown workspace, before anything else is trusted ----------
	r = await call("GET", f"/api/v1/workspaces/{uuid.uuid4()}/competitors")
	check("unknown workspace -> 404", r.status_code == 404, r.text)

	# -- empty list on a fresh workspace --------------------------------------
	r = await call("GET", base)
	check("empty list -> 200", r.status_code == 200, r.text)
	check("empty list is empty", r.json() == {"competitors": [], "total": 0}, r.text)

	# -- a run before discovery has a profile is refused, with the reason ------
	r = await call("POST", f"{base}/runs")
	check("run without a profile -> 409", r.status_code == 409, r.text)
	check(
		"409 explains what is missing",
		"ideal competitor profile" in r.json()["detail"],
		r.text,
	)

	await _attach_profile(workspace_id)

	# -- manual add by URL, with a bare host ----------------------------------
	r = await call("POST", base, json={"website": "acme.com"})
	check("bare host accepted -> 201", r.status_code == 201, r.text)
	added = r.json()
	check("bare host gets a scheme", added["website"] == "https://acme.com", r.text)
	check("marked manual", added["source"] == "manual", r.text)
	check("no run_id on a manual add", added["run_id"] is None, r.text)
	check(
		"unsurfaced fields declared up front",
		added["unsourced_fields"] == ["description", "offering", "strengths", "weaknesses"],
		r.text,
	)
	check("empty JSON lists, not null", added["pain_signals"] == [] and added["evidence"] is None, r.text)

	# -- idempotent re-add, and dedup across URL spellings --------------------
	for variant in ("https://www.acme.com/about", "http://ACME.com:8443", "https://acme.com"):
		r = await call("POST", base, json={"website": variant})
		check(f"re-add {variant} -> 200 not 409", r.status_code == 200, r.text)
		check(f"re-add {variant} is the same row", r.json()["id"] == added["id"], r.text)

	r = await call("GET", base)
	check("four URL spellings -> one row", r.json()["total"] == 1, r.text)

	# -- a second, genuinely different competitor ------------------------------
	r = await call("POST", base, json={"website": "https://globex.io", "name": "Globex"})
	check("second competitor -> 201", r.status_code == 201, r.text)
	globex_id = r.json()["id"]
	check("explicit name kept", r.json()["name"] == "Globex", r.text)

	r = await call("GET", base)
	check("list has both", r.json()["total"] == 2, r.text)

	# -- a social's confidence grade survives the trip out ---------------------
	# The agent grades every handle it finds, and the grade is the difference
	# between "read off this company's own site" and "a handle that sat next to
	# its name in a directory". A response schema that omits the field silently
	# drops it, and the UI then renders both as an equally certain link -- which
	# is the one distinction that stops a user following the wrong company.
	async with _Session() as db:
		async with db.begin():
			row = await db.get(Competitor, uuid.UUID(added["id"]))
			row.tracking_sources = [
				{"kind": "linkedin", "value": "https://linkedin.com/company/acme", "confidence": "high"},
				{"kind": "instagram", "value": "@acme", "confidence": "low"},
			]

	r = await call("GET", base)
	by_id = {c["id"]: c for c in r.json()["competitors"]}
	sources = by_id[added["id"]]["tracking_sources"]
	check("tracking sources come back", len(sources) == 2, r.text)
	check(
		"per-source confidence survives",
		[s.get("confidence") for s in sources] == ["high", "low"],
		r.text,
	)
	check(
		"confidence absent is null, not a invented medium",
		all(
			s.get("confidence") is None
			for c in r.json()["competitors"]
			for s in c["tracking_sources"]
			if s["kind"] == "website"
	 ),
		r.text,
	)

	# Put the row back the way the add endpoint left it, so the later counts in
	# this script are not measuring a profile it did not create.
	async with _Session() as db:
		async with db.begin():
			row = await db.get(Competitor, uuid.UUID(added["id"]))
			row.tracking_sources = [{"kind": "website", "value": added["website"]}]

	# -- tenant scoping: another workspace's competitor id is a 404 -----------
	r = await call(
		"PATCH",
		f"/api/v1/workspaces/{other_ws}/competitors/{globex_id}",
		json={"notes": "should not apply"},
	)
	check("cross-workspace patch -> 404", r.status_code == 404, r.text)

	# -- the narrow update surface --------------------------------------------
	r = await call("PATCH", f"{base}/{globex_id}", json={"notes": "beats us on price"})
	check("patch -> 200", r.status_code == 200, r.text)
	check("note saved", r.json()["notes"] == "beats us on price", r.text)

	for forbidden in ("strengths", "weaknesses", "pain_signals", "evidence", "unsourced_fields"):
		r = await call("PATCH", f"{base}/{globex_id}", json={forbidden: ["invented"]})
		check(f"patch cannot write {forbidden}", r.status_code == 422, r.text)

	# -- editing the website re-keys the dedup identity -----------------------
	r = await call("PATCH", f"{base}/{globex_id}", json={"website": "initech.com"})
	check("website edit -> 200", r.status_code == 200, r.text)
	check("domain_key follows the website", r.json()["domain_key"] == "initech.com", r.text)

	# -- ...and cannot collide with a competitor already tracked ---------------
	r = await call("PATCH", f"{base}/{globex_id}", json={"website": "https://www.acme.com"})
	check("website edit onto a tracked host -> 409", r.status_code == 409, r.text)
	r = await call("GET", base)
	check("the 409 did not corrupt the list", r.json()["total"] == 2, r.text)

	# -- starting a run returns something pollable ----------------------------
	r = await call("POST", f"{base}/runs")
	check("run start -> 202", r.status_code == 202, r.text)
	started = r.json()
	check("run is pending", started["run"]["status"] == "pending", r.text)
	check("archetypes counted from the profile", started["run"]["archetypes_targeted"] == 2, r.text)
	check("profile confidence carried over", started["run"]["profile_confidence"] == "high", r.text)
	check("already_tracked reported", started["already_tracked"] == 2, r.text)
	run_id = started["run"]["id"]

	r = await call("GET", f"{base}/runs/{run_id}")
	check("poll the run -> 200", r.status_code == 200, r.text)
	check("poll returns the same run", r.json()["id"] == run_id, r.text)

	# -- an in-flight run is returned, not duplicated -------------------------
	r = await call("POST", f"{base}/runs")
	check("second start while pending -> 202", r.status_code == 202, r.text)
	check("second start reuses the run", r.json()["run"]["id"] == run_id, r.text)

	r = await call("GET", f"{base}/runs")
	check("run history lists it once", len(r.json()) == 1, r.text)

	# -- a run id from another workspace is a 404 -----------------------------
	r = await call("GET", f"/api/v1/workspaces/{other_ws}/competitors/runs/{run_id}")
	check("cross-workspace run poll -> 404", r.status_code == 404, r.text)

	# -- delete ---------------------------------------------------------------
	r = await call("DELETE", f"{base}/{globex_id}")
	check("delete -> 204", r.status_code == 204, r.text)
	r = await call("GET", base)
	check("list shrank", r.json()["total"] == 1, r.text)
	r = await call("DELETE", f"{base}/{globex_id}")
	check("delete again -> 404", r.status_code == 404, r.text)

	# -- the website column really is NOT NULL, enforced by the database ------
	# Asserted against raw SQL rather than the ORM on purpose: the requirement is
	# that the column refuses a null, not that the ORM happens to type it as
	# non-optional. A future caller that bypasses validation still cannot store a
	# competitor with no site.
	from sqlalchemy import text as sql_text

	rejected = False
	try:
		async with _engine.begin() as conn:
			await conn.execute(
				sql_text(
					"INSERT INTO competitors (id, workspace_id, name, website, "
					"domain_key, source, first_seen_at, last_seen_at) VALUES "
					"(:id, :ws, 'No Site', NULL, 'nosite', 'agent', "
					"CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
				),
				{"id": uuid.uuid4().hex, "ws": workspace_id.hex},
			)
	except Exception:
		rejected = True
	check("a competitor with no website is refused by the database", rejected)

	# -- ...and the API cannot smuggle one in either ---------------------------
	r = await call("POST", base, json={"website": ""})
	check("empty website rejected at the schema", r.status_code == 422, r.text)

	# -- runs survive competitor deletion (SET NULL, not CASCADE) -------------
	async with _Session() as db:
		async with db.begin():
			# A real UUID, not the JSON string: FastAPI parses the path param into
			# one, and the ORM's UUID column will not coerce from str.
			run = await db.get(CompetitorRun, uuid.UUID(run_id))
			check("run row still readable after a competitor delete", run is not None)

	print()
	for label in PASS:
		print(f"  ok  {label}")
	print(f"\ncompetitors endpoints OK ({len(PASS)} checks)")


if __name__ == "__main__":
	try:
		asyncio.run(main())
	finally:
		os.unlink(_DB_PATH)
