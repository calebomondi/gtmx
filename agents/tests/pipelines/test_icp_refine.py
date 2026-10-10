"""ICP finalization: the refine pass patches the draft instead of regenerating
it, falls back to a full build without a draft, and the parallel draft step
soft-fails."""

from agents import discovery_agent
from agents.pipelines.discover import build_icp
from agents.schemas.icp import ICP, ICPRevision

DRAFT = ICP(
    product_name="Linear",
    buyer_type="b2b",
    industries=["Software", "Fintech", "Health", "Retail"],
    beachhead="Series A dev teams",
    competitor_leads=[],
)
STATE = {"offer_type": "product", "offer_name": "Linear", "icp_data": DRAFT}


def _stub(monkeypatch, result):
    calls = []

    def fake(messages, schema=None, **kw):
        calls.append((schema, messages[0].content))
        return result
    monkeypatch.setattr(build_icp, "invoke_structured_with_fallback", fake)
    return calls


def test_refine_patches_only_changed_fields(monkeypatch):
    calls = _stub(monkeypatch, ICPRevision(
        beachhead="Seed-stage AI startups",
        competitor_leads=[{"competitor_name": "Rival", "search_queries": ["q"], "pain_angles": ["p"]}],
    ))
    final = build_icp.refine_icp(STATE)["icp_data"]
    assert calls[0][0] is ICPRevision
    assert "return ONLY the fields you change" in calls[0][1]
    assert final.beachhead == "Seed-stage AI startups"
    assert [lead.competitor_name for lead in final.competitor_leads] == ["Rival"]
    assert final.product_name == "Linear"  # untouched fields survive
    assert final.industries == ["Software", "Fintech", "Health"]  # clamp still applies


def test_refine_with_no_changes_keeps_draft(monkeypatch):
    _stub(monkeypatch, ICPRevision())
    final = build_icp.refine_icp(STATE)["icp_data"]
    assert final.beachhead == DRAFT.beachhead


def test_refine_without_draft_builds_whole_icp(monkeypatch):
    calls = _stub(monkeypatch, DRAFT)
    final = build_icp.refine_icp({**STATE, "icp_data": None})["icp_data"]
    assert calls[0][0] is ICP and "complete ICP" in calls[0][1]
    assert final.product_name == "Linear"


def test_parallel_draft_soft_fails(monkeypatch):
    def boom(state):
        raise RuntimeError("provider down")
    monkeypatch.setattr(discovery_agent, "create_icp", boom)
    assert discovery_agent.run_draft_icp({}) == {}
