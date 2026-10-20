"""Finding customers for a Lace: v1's discovery on the Lace's ICP, a fit case
per account, and the tools that start and read it."""

import json

from agents.lace.accounts import find_accounts, record_brief
from agents.lace.tools import build_tools
from agents.schemas.accounts import AccountFit, AccountList, AccountRecord, TriggerEvent
from agents.schemas.icp import ICP
from agents.schemas.lace import AccountSummary, LaceProfile
from lace_fakes import MemoryStore, RecordingJobs, make_fact

PROFILE = LaceProfile(name="Ada", website="https://acme.test", startup_name="Acme")
ICP_IN = ICP(buyer_type="b2b", industries=["Clinics"], geo=["Kenya", "Uganda"])


def _account(name: str) -> AccountRecord:
    return AccountRecord(name=name, website=f"https://{name.lower()}.test", summary="A clinic chain.",
                         trigger_event=TriggerEvent(event="Opened 3 new sites", signal_type="hiring_post",
                                                    source="https://news.test/1"))


FIT = AccountFit(need="Payroll across new sites", capability="Multi-site payroll", payoff="Staff paid on time",
                 angle="Three new sites, one payroll.", strength="strong")


def test_discovery_runs_on_the_icp_and_each_account_gets_a_case():
    seen = {}

    def discover(state):
        seen.update(state)
        return {"accounts": AccountList(accounts=[_account("Alpha"), _account("Beta")])}

    def assess(offer, account, seller):
        if "Beta" in account:
            raise RuntimeError("provider down")
        seen["offer"], seen["seller"] = offer, seller
        return FIT

    found = find_accounts(PROFILE, [make_fact("1", "Acme sells payroll to clinics.")], ICP_IN, ["acme.test", "rival.test"],
                          country="Kenya", discover=discover, assess=assess)
    assert [(r.name, f) for r, f in found] == [("Alpha", FIT), ("Beta", None)]
    assert {r.geo for r, _ in found} == {"Kenya"}
    assert seen["icp_data"].geo == ["Kenya"] and seen["target_market"] == ["Kenya"]
    assert seen["exclude_domains"] == ["acme.test", "rival.test"] and seen["offer_name"] == "Acme"
    assert "payroll to clinics" in seen["offer"] and seen["seller"] == "Acme"


def test_without_a_country_every_icp_geography_is_searched():
    seen = {}
    find_accounts(PROFILE, [], ICP_IN, [], discover=lambda s: seen.update(s) or {}, assess=lambda *a: FIT)
    assert seen["target_market"] == ["Kenya", "Uganda"]


def test_record_brief_carries_the_trigger():
    brief = record_brief(_account("Alpha"))
    assert "Trigger event: Opened 3 new sites (source: https://news.test/1)" in brief


async def test_find_accounts_starts_without_an_icp(settings):
    """The search works out an ICP itself when there is none, in the
    background, so the turn never waits minutes on it."""
    jobs = RecordingJobs()
    tool = {t.name: t for t in build_tools(MemoryStore(), settings, jobs)}["find_accounts"]
    assert json.loads(await tool.ainvoke({"country": "Kenya"}))["ok"]
    assert jobs.started == [("find_accounts", {"country": "Kenya"})]


async def test_list_accounts(settings):
    store = MemoryStore()
    store.targets = [AccountSummary(id="a1", name="Alpha", account_type="company", trigger="Opened 3 new sites",
                                    need="Payroll", fit_strength="strong")]
    out = json.loads(await {t.name: t for t in build_tools(store, settings)}["list_accounts"].ainvoke({}))
    assert out["summary"] == "1 target accounts." and out["data"][0]["trigger"] == "Opened 3 new sites"
