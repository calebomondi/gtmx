"""The Lace's competitor hunt: briefed from facts into v1's pipeline, and
started as a background job from a tool."""

import json

import pytest

from agents.lace.competitors import find_competitors
from agents.lace.tools import build_tools
from agents.schemas.competition import ArchetypeSketch, CompetitorProfile, ProfileSkeleton
from agents.schemas.lace import CompetitorHuntBrief, CompetitorSummary, LaceProfile
from lace_fakes import MemoryStore, RecordingJobs, make_fact

PROFILE = LaceProfile(name="Ada", website="https://acme.test", startup_name="Acme")
FACTS = [make_fact("1", "Acme sells payroll software to clinics in Kenya.")]


def _brief(archetypes=("Clinic payroll SaaS",)):
    return lambda messages: CompetitorHuntBrief(
        offer_summary="Payroll software for clinics.",
        target_geographies=["Kenya"],
        profile=ProfileSkeleton(archetypes=[ArchetypeSketch(label=a, archetype_description="x", geography_scope="local")
                                            for a in archetypes]),
    )


def test_hunt_runs_v1_with_a_brief_drawn_from_facts():
    seen = {}

    def hunt(state):
        seen.update(state)
        return {"competitor_profiles": [CompetitorProfile(name="Rival", website="https://rival.test")]}

    out = find_competitors(PROFILE, FACTS, focus="local players", brief=_brief(), hunt=hunt)
    assert [p.name for p in out] == ["Rival"]
    assert seen["own_website"] == "https://acme.test" and seen["offer_name"] == "Acme"
    assert seen["target_market"] == ["Kenya"]
    assert [a["label"] for a in seen["ideal_competitor_profile"]["archetypes"]] == ["Clinic payroll SaaS"]


def test_focus_and_facts_reach_the_brief():
    seen = {}

    def brief(messages):
        seen["prompt"] = messages[0].content
        return _brief()(messages)

    find_competitors(PROFILE, FACTS, focus="AI-first tools", brief=brief, hunt=lambda s: {})
    assert "AI-first tools" in seen["prompt"] and "payroll software to clinics" in seen["prompt"]


def test_no_archetypes_is_an_error_not_an_empty_hunt():
    with pytest.raises(ValueError, match="Not enough is known"):
        find_competitors(PROFILE, FACTS, brief=_brief(archetypes=()), hunt=lambda s: pytest.fail("hunted"))


async def test_find_competitors_tool_starts_a_job(settings):
    jobs = RecordingJobs()
    tool = {t.name: t for t in build_tools(MemoryStore(), settings, jobs)}["find_competitors"]
    out = json.loads(await tool.ainvoke({"focus": "local players"}))
    assert out["ok"] and "few minutes" in out["summary"]
    assert jobs.started == [("find_competitors", {"focus": "local players"})]


async def test_a_refused_job_is_reported(settings):
    tool = {t.name: t for t in build_tools(MemoryStore(), settings, RecordingJobs(refuse="Already searching."))}
    out = json.loads(await tool["find_competitors"].ainvoke({}))
    assert out == {"ok": False, "summary": "Already searching.", "error": "Already searching."}


def test_job_tools_need_a_job_runner(settings):
    assert "find_competitors" not in {t.name for t in build_tools(MemoryStore(), settings)}


async def test_list_competitors(settings):
    store = MemoryStore()
    store.tracked = [CompetitorSummary(id="c1", name="Rival", website="https://rival.test",
                                       summary="Payroll for vets.", origin="found", status="tracked")]
    tool = {t.name: t for t in build_tools(store, settings)}["list_competitors"]
    out = json.loads(await tool.ainvoke({}))
    assert out["summary"] == "1 competitors tracked." and out["data"][0]["name"] == "Rival"


async def test_check_competitors_tool_starts_a_check(settings):
    jobs = RecordingJobs()
    tool = {t.name: t for t in build_tools(MemoryStore(), settings, jobs)}["check_competitors"]
    assert json.loads(await tool.ainvoke({}))["ok"]
    assert jobs.started == [("check_competitors", {})]


def test_only_material_sourced_changes_become_facts():
    from agents.lace.competitors import change_fact, material
    from agents.schemas.monitor import CompetitorChange
    big = CompetitorChange(kind="pricing", title="Cut Pro to $8", summary="Undercuts us.", importance="high",
                           source_url="https://rival.test/pricing")
    small = CompetitorChange(kind="social", title="Posted a meme", summary="Noise.", importance="low")
    unsourced = CompetitorChange(kind="news", title="Rumoured raise", summary="?", importance="medium")
    assert material([big, small, unsourced]) == [big, unsourced]
    fact = change_fact("Rival", big)
    assert fact.claim == "Rival: Cut Pro to $8. Undercuts us." and fact.origin == "monitor"
    assert fact.topic == "competition" and fact.source_url == "https://rival.test/pricing"
    assert change_fact("Rival", unsourced) is None
