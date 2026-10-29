"""The Lace's ICP: drawn from facts with the founder's word first, saved on
the Lace, and carried in every system prompt."""

import json
from datetime import datetime, timezone

from agents.lace.icp import define_icp
from agents.lace.prompts import render_brief, render_icp, system_prompt
from agents.lace.tools import build_tools
from agents.schemas.icp import ICP
from agents.schemas.lace import CompetitorSummary, Fact, LaceProfile
from lace_fakes import MemoryStore, RecordingJobs, make_fact

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


async def test_the_tool_works_it_out_in_the_background(settings):
    jobs = RecordingJobs()
    tool = {t.name: t for t in build_tools(MemoryStore(), settings, jobs)}["define_icp"]
    out = json.loads(await tool.ainvoke({"guidance": "clinics"}))
    assert out["ok"] and "few minutes" in out["summary"]
    assert jobs.started == [("define_icp", {"guidance": "clinics"})]
    # Without a way to run jobs there is no tool to start one.
    assert "define_icp" not in {t.name for t in build_tools(MemoryStore(), settings)}


def test_the_prompt_carries_the_icp_or_says_there_is_none():
    assert "Not defined yet" in render_icp(None)
    gist = render_icp(ICP_OUT)
    assert "- Industries: Private clinics" in gist and "- Start with: Multi-site clinics in Nairobi" in gist
    assert "- Not: Hospitals" in gist
    assert "Multi-site clinics in Nairobi" in system_prompt(PROFILE, [], ICP_OUT)


def test_the_prompt_says_what_is_on_file_and_to_speak_as_itself():
    from agents.lace.prompts import render_on_file
    from agents.schemas.lace import Suggestions
    rivals = [CompetitorSummary(id=f"c{i}", name=f"Rival {i}", website="https://r.test", origin="found", status="tracked")
              for i in range(10)]
    on_file = render_on_file(rivals, [], [], Suggestions())
    assert "- Competitors you track: Rival 0, Rival 1" in on_file and "(+2 more)" in on_file
    assert "- Leads saved: none yet" in on_file
    prompt = system_prompt(PROFILE, [], on_file=on_file)
    assert "Rival 7" in prompt and '"we", "us" and "our"' in prompt and "Never claim an absence" in prompt
    assert "say why it fits" in prompt
