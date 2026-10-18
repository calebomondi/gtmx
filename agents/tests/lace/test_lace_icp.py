"""The Lace's ICP: drawn from facts with the founder's word first, saved on
the Lace, and carried in every system prompt."""

import json
from datetime import datetime, timezone

from agents.lace.icp import define_icp
from agents.lace.prompts import render_brief, render_icp, system_prompt
from agents.lace.tools import build_tools
from agents.schemas.icp import ICP
from agents.schemas.lace import CompetitorSummary, Fact, LaceProfile
from lace_fakes import MemoryStore, make_fact

PROFILE = LaceProfile(name="Ada", website="https://acme.test", startup_name="Acme")
ICP_OUT = ICP(buyer_type="b2b", industries=["Private clinics"], company_sizes=["10-50"], geo=["Kenya"],
              buyer_titles=["Clinic owner"], beachhead="Multi-site clinics in Nairobi", exclusions=["Hospitals"])


def _founder_fact(claim: str) -> Fact:
    return Fact(id="u1", topic="icp", claim=claim, origin="user", confidence="high",
                recorded_at=datetime.now(timezone.utc))


def test_founder_facts_come_first_and_are_marked():
    brief = render_brief([make_fact("1", "Sells to hospitals.", topic="icp"), _founder_fact("We sell to clinics.")])
    assert brief.splitlines()[0] == "- [icp] (the founder said) We sell to clinics."


def test_define_icp_sees_facts_competitors_and_guidance():
    seen = {}

    def draft(messages):
        seen["prompt"] = messages[0].content
        return ICP_OUT

    rivals = [CompetitorSummary(id="c", name="Rival", website="https://rival.test", summary="Payroll for vets.",
                                origin="found", status="tracked")]
    icp = define_icp(PROFILE, [_founder_fact("We sell to clinics.")], rivals, "focus on Nairobi", draft)
    assert icp.product_name == "Acme" and icp.industries == ["Private clinics"]
    assert "(the founder said) We sell to clinics." in seen["prompt"]
    assert "Rival (https://rival.test): Payroll for vets." in seen["prompt"]
    assert "focus on Nairobi" in seen["prompt"]


async def test_tool_saves_the_icp(settings, monkeypatch):
    from agents.lace import icp as lace_icp
    monkeypatch.setattr(lace_icp, "define_icp", lambda profile, facts, rivals, guidance: ICP_OUT)
    store = MemoryStore()
    tool = {t.name: t for t in build_tools(store, settings)}["define_icp"]
    out = json.loads(await tool.ainvoke({"guidance": "clinics"}))
    assert out["ok"] and out["data"]["industries"] == ["Private clinics"]
    assert store.saved_icp == ICP_OUT


def test_the_prompt_carries_the_icp_or_says_there_is_none():
    assert "Not defined yet" in render_icp(None)
    gist = render_icp(ICP_OUT)
    assert "- Industries: Private clinics" in gist and "- Start with: Multi-site clinics in Nairobi" in gist
    assert "- Not: Hospitals" in gist
    assert "Multi-site clinics in Nairobi" in system_prompt(PROFILE, [], ICP_OUT)
