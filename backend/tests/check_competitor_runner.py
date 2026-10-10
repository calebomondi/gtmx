"""Exercise the competitor runner end-to-end against a real database.

The agent's own screening is covered by dry_run_get_competitors.py. What is left
untested is the half that only fails against real SQL: hydration from a workspace,
the upsert, and -- the claim the whole "runnable repeatedly, each run appends"
requirement rests on -- that a second run REFRESHES a known company rather than
duplicating it or clobbering a user's manual row.

Stubs the agent's network and LLM; uses a real SQLite file and real sessions.

Run directly (pytest is not installed in this venv):
    PYTHONPATH=/home/mokuaxv/gtmx2/gtmx .venv/bin/python \
        backend/app/_check_competitor_runner.py
"""

import asyncio
import os
import sys
import tempfile
import uuid

# Make `backend.app.*` and the root `config` importable when run directly.
# Matches the sys.path handling in test_projects_api.py.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import httpx
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agents.sub_agents.schema_states import CandidateFinding, CompetitorProfile, SourcedFinding

from backend.app.api.v1.routes import api_router
from backend.app.database import models  # noqa: F401 -- registers the tables
from backend.app.database.connect import Base, get_db
from backend.app.database.models import Competitor, User, Workspace

_DB_PATH = tempfile.mkstemp(suffix=".db")[1]
_engine = create_async_engine(f"sqlite+aiosqlite:///{_DB_PATH}")
_Session = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

PASS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
	if not condition:
		raise AssertionError(f"{label}{(' -- ' + detail) if detail else ''}")
	PASS.append(label)


# --------------------------------------------------------------------------
# Stub the agent. One canned firm on run 1, two on run 2, so the second run has
# both something new to append and something known to refresh.
# --------------------------------------------------------------------------

_RUN = {"names": ["Acme Vector"]}


def _install_agent_stubs():
	import data_sources.scraping.exa as exa

	import agents.sub_agents.competitors.get_competitors as gc

	exa.search_and_scrape = lambda *a, **k: [
		{"url": "https://directory.example/list", "title": "Rivals", "text": "canned"}
	]
	exa.scrape_url = lambda url, config: f"[site] {url} text"
	gc.search_and_scrape = exa.search_and_scrape
	gc.scrape_url = exa.scrape_url
	gc.distill_documents = lambda docs, focus, log_label="d": "canned notes"

	def _fake_llm(messages, schema=None, **kw):
		name = getattr(schema, "__name__", "")
		if name == "CompetitorHuntPlan":
			return schema(
				tasks=[
				 gc_t("Local incumbent", "local", ["vector database companies Kenya"]),
				 gc_t("Global incumbent", "global", ["enterprise vector database vendors"]),
				]
			)
		if name == "CandidateFinding":
			return [
				CandidateFinding(name=n, website=f"https://{n.split()[0].lower()}.com")
				for n in _RUN["names"]
			]
		if name == "CompetitorProfile":
			return CompetitorProfile(
				name="profiled",
				website="will-be-overwritten",
				description="canned description",
				pricing="$99/mo",
				strengths=[SourcedFinding(text="fast", evidence='"2ms"', source_url="https://x.example/bench")],
				opportunities=["Undercut on price"],
				tracking_sources=[{"kind": "linkedin", "value": "https://linkedin.com/company/x", "confidence": "high"}],
				evidence={"pricing": ["https://x.example/pricing"]},
				unsourced_fields=["pricing", "headquarters"],
			)
		return None

	gc.invoke_structured_with_fallback = _fake_llm


def gc_t(label, geo, queries):
	from agents.sub_agents.schema_states import CompetitorHuntTask

	return CompetitorHuntTask(
		archetype_label=label, geography_scope=geo, objective="find", queries=queries
	)


async def _seed_workspace(include_profile: bool = True, with_archetypes: bool = True) -> uuid.UUID:
	async with _Session() as db:
		async with db.begin():
			user = User(id=uuid.uuid4(), name="Founder", email=f"{uuid.uuid4().hex}@e.com")
			db.add(user)
			await db.flush()
			workspace = Workspace(name="HeatherDB", user_id=user.id)
			db.add(workspace)
			await db.flush()
			wid = workspace.id

	if include_profile:
		insights = {
			"offer_type": "product",
			"offer_snapshot": {
				"offer_name": "Heather",
				"offer_description": "A vector database",
				"problem_solved": "slow search",
				"how_it_works": "index and query",
				"website_url": "https://heather.dev",
				"features": [{"name": "low latency"}, {"name": "on-prem"}],
			},
		}
		if with_archetypes:
			insights["ideal_competitor_profile"] = {
				"category_definition": "vector databases",
				"archetypes": [
					{"label": "Local incumbent", "geography_scope": "local"},
					{"label": "Global incumbent", "geography_scope": "global"},
				],
				"confidence": "high",
			}
		async with _Session() as db:
			async with db.begin():
				db.add(models.ProductProfile(workspace_id=wid, product_name="Heather", insights=insights))
	return wid


async def _list_via_api(workspace_id: uuid.UUID) -> dict:
	app = FastAPI()
	app.include_router(api_router, prefix="/api/v1")

	async def _db():
		async with _Session() as session:
			yield session

	app.dependency_overrides[get_db] = _db
	async with httpx.AsyncClient(
		transport=httpx.ASGITransport(app=app), base_url="http://t"
	) as client:
		r = await client.get(f"/api/v1/workspaces/{workspace_id}/competitors")
		return r.json()


async def main() -> None:
	async with _engine.begin() as conn:
		await conn.run_sync(Base.metadata.create_all)

	import backend.app.competitor_runner as runner

	# Point the runner at the isolated session.
	runner.AsyncSessionLocal = _Session
	_install_agent_stubs()

	# -- a workspace with no profile at all is a clear setup error ---------
	bare = await _seed_workspace(include_profile=False)
	try:
		await runner.run_competitor_discovery(bare)
	except ValueError as exc:
		check("a workspace with no profile raises a setup error", "discovery" in str(exc), str(exc))
	else:
		raise AssertionError("a workspace with no profile was hunted anyway")

	# -- a profile with no archetypes is refused, not guessed at ------------
	shapeless = await _seed_workspace(with_archetypes=False)
	try:
		await runner.run_competitor_discovery(shapeless)
	except ValueError as exc:
		check("a profile with no archetypes is refused", "ideal competitor profile" in str(exc), str(exc))
	else:
		raise AssertionError("a shapeless profile was hunted anyway")

	# -- the happy path ----------------------------------------------------
	wid = await _seed_workspace()
	run_id = uuid.uuid4()

	first = await runner.run_competitor_discovery(workspace_id=wid, run_id=run_id)
	check("run 1 found competitors", first["found"] >= 1, str(first))
	check("run 1 inserted them", first["inserted"] >= 1, str(first))
	check("run 1 refreshed nothing", first["refreshed"] == 0, str(first))
	check("run 1 screened candidates", first["candidates_seen"] >= 1, str(first))
	check(
		"run 1 dropped the directory-shaped candidates",
		first["dropped"] >= 1,
		str(first),
	)

	listed = await _list_via_api(wid)
	check("the API sees them", listed["total"] == first["found"], str(listed["total"]))
	acme = next((c for c in listed["competitors"] if c["domain_key"] == "acme.com"), None)
	check("the canned firm is stored", acme is not None, str(listed))
	if acme:
		check("it is attributed to the run", acme["run_id"] == str(run_id))
		check("it is marked agent-sourced", acme["source"] == "agent")
		check("the profiler could not overwrite the website", acme["website"] == "https://acme.com", acme["website"])
		check("its description came through", acme["description"] == "canned description")
		check("its social came through", len(acme["tracking_sources"]) == 1)
		check("its opportunity came through", len(acme["opportunities"]) == 1)
		check("its weakness evidence survived", acme["strengths"][0]["evidence"] == '"2ms"', str(acme["strengths"]))
		check(
			"a filled field is not left declared unsourced",
			"pricing" not in acme["unsourced_fields"],
			str(acme["unsourced_fields"]),
		)
		check(
			"a genuinely unfilled field is",
			"headquarters" in acme["unsourced_fields"],
			str(acme["unsourced_fields"]),
		)

	# -- re-running appends, and refreshes what it already knows -----------
	_RUN["names"] = ["Acme Vector", "Globex"]
	second = await runner.run_competitor_discovery(workspace_id=wid, run_id=uuid.uuid4())

	check("run 2 inserted the new firm", second["inserted"] == 1, str(second))
	check("run 2 refreshed the known one", second["refreshed"] >= 1, str(second))

	listed2 = await _list_via_api(wid)
	check("the list grew", listed2["total"] == 2, str(listed2["total"]))
	check(
		"no duplicate for the re-found firm",
		len([c for c in listed2["competitors"] if c["domain_key"] == "acme.com"]) == 1,
		str([c["domain_key"] for c in listed2["competitors"]]),
	)
	acme2 = next(c for c in listed2["competitors"] if c["domain_key"] == "acme.com")
	check(
		"the re-found firm keeps its ORIGINAL run attribution",
		acme2["run_id"] == str(run_id),
		f"{acme2['run_id']} vs {run_id}",
	)
	check(
		"the re-found firm keeps its first_seen_at",
		acme2["first_seen_at"] == acme["first_seen_at"],
		acme2["first_seen_at"],
	)

	# -- a manual row survives an agent run, provenance and notes intact ---
	async with _Session() as db:
		async with db.begin():
			db.add(
				Competitor(
					workspace_id=wid,
					name="Manual Co",
					website="https://manual.com",
					domain_key="manual.com",
					source="manual",
					notes="beats us on price",
				)
			)

	_RUN["names"] = ["Acme Vector", "Globex"]
	await runner.run_competitor_discovery(workspace_id=wid, run_id=uuid.uuid4())

	listed3 = await _list_via_api(wid)
	manual = next(c for c in listed3["competitors"] if c["domain_key"] == "manual.com")
	check("the manual row is still there", manual is not None)
	check("it is still marked manual", manual["source"] == "manual", manual["source"])
	check("its note survived", manual["notes"] == "beats us on price", str(manual["notes"]))
	check("it was never attributed to a run", manual["run_id"] is None, str(manual["run_id"]))
	# The run re-found only the two agent-known firms, so the manual row must be
	# untouched AND uncounted: 2 agent-found + 1 manual.
	check("the manual row was not re-found by the run", listed3["total"] == 3, str(listed3["total"]))
	check(
		"both agent firms are still there",
		{"acme.com", "globex.com"} <= {c["domain_key"] for c in listed3["competitors"]},
		str([c["domain_key"] for c in listed3["competitors"]]),
	)

	# -- the preserved-field guard actually fires -------------------------
	from agents.sub_agents.competitors.get_competitors import row_values_from_profile

	poisoned = row_values_from_profile(
		CompetitorProfile(name="X", website="https://x.com")
	)
	poisoned["source"] = "manual"
	poisoned["notes"] = "smuggled"
	try:
		async with _Session() as db:
			async with db.begin():
				await runner._upsert_profiles(db, wid, uuid.uuid4(), [poisoned])
	except ValueError as exc:
		check("a row smuggling provenance fields is refused", "preserved field" in str(exc), str(exc))
	else:
		raise AssertionError("a row overwriting source/notes was accepted")

	# -- the manual deep-research path -------------------------------------
	app = FastAPI()
	app.include_router(api_router, prefix="/api/v1")

	async def _db():
		async with _Session() as session:
			yield session

	app.dependency_overrides[get_db] = _db
	async with httpx.AsyncClient(
		transport=httpx.ASGITransport(app=app), base_url="http://t"
	) as client:
		r = await client.post(
			f"/api/v1/workspaces/{wid}/competitors",
			json={"website": "https://added-by-hand.com", "name": "Added By Hand"},
		)
		check("manual add -> 201", r.status_code == 201, r.text)
		added = r.json()
		# A real UUID, not the JSON string: FastAPI parses the path param into
		# one, and the ORM's UUID column will not coerce from str.
		added_uuid = uuid.UUID(added["id"])

		ok = await runner.research_competitor_site(wid, added_uuid)
		check("the manual deep-research path ran", ok is True)

	async with _Session() as db:
		async with db.begin():
			row = await db.get(Competitor, added_uuid)
			check("it was researched in place", row.description == "canned description", str(row.description))
			check("it kept its website", row.website == "https://added-by-hand.com", row.website)
			check("it is still marked manual", row.source == "manual", row.source)
			check("it is stamped as researched", row.deep_researched_at is not None)

		missing = await runner.research_competitor_site(wid, uuid.uuid4())
		check("researching a competitor that is gone returns False", missing is False)

	print()
	for label in PASS:
		print(f"  ok  {label}")
	print(f"\ncompetitor runner OK ({len(PASS)} checks)")


if __name__ == "__main__":
	try:
		asyncio.run(main())
	finally:
		_engine.dispose()
		os.unlink(_DB_PATH)