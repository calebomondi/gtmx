"""Standalone harness for agents/pipelines/account_discovery.py.

Run:
    PYTHONPATH=/home/mokuaxv/gtmx2/gtmx .venv/bin/python \
        agents/tests/pipelines/live_account_discovery.py
"""
import os
import sys
from pathlib import Path

# Walk up from cwd to find repo root (has pyproject.toml).
root = Path.cwd()
while root != root.parent:
    if (root / "pyproject.toml").exists():
        break
    root = root.parent
sys.path.insert(0, str(root))

import agents.pipelines.accounts.account_discovery as discovery
from agents.pipelines.accounts.account_discovery import run_account_discovery
from agents.pipelines.discover.build_icp import build_icp_graph
from agents.schemas.sessions import IcpSessionState
from agents.schemas.accounts import AccountList, AccountRecord, SourceRecord, TriggerEvent
from agents.schemas.icp import ICP
from agents.tests.pipelines.test_build_icp import BRANCHES


def _deterministic_account(name: str, domain: str) -> AccountRecord:
    return AccountRecord(
        name=name,
        account_type="company",
        website=None,
        domain=None,
        geo="Kenya",
        trigger_event=TriggerEvent(
            event="hiring burst visible on LinkedIn",
            signal_type="hiring_post",
            source="https://example.com/hiring-burst",
        ),
        sources=[SourceRecord(title="Hiring burst", url="https://example.com/hiring-burst")],
        key_contacts=[],
        socials={},
    )


def run_deterministic_checks() -> None:
    """Fast fixture run of the whole graph plus strict-gate sanity checks."""
    print("\n### Deterministic fixture checks ###")
    original_search = discovery.search_and_scrape
    original_invoke = discovery.invoke_structured_with_fallback
    original_linkedin_get_company = discovery.linkedin.get_company
    original_instagram_get_profile = discovery.instagram.get_profile
    original_tiktok_get_profile = discovery.tiktok.get_profile
    original_x_get_profile = discovery.x.get_profile
    saw_thinking_override = None

    def fake_search_and_scrape(query: str, config, num_results: int = 5, start_published_date=None):
        text: str
        url: str
        if 'official website' in query:
            text = 'Foo Inc official website. Contact: hello@foo.com. LinkedIn: https://www.linkedin.com/company/foo-inc'
            url = 'https://foo.com'
        elif 'site:linkedin.com/company' in query:
            text = 'Foo Inc on LinkedIn'
            url = 'https://www.linkedin.com/company/foo-inc'
        elif 'email' in query:
            text = 'Reach us at hello@foo.com or +254 700 000 000'
            url = 'https://foo.com/contact'
        else:
            text = f'{config.get("market_recency_days", 365) if isinstance(config, dict) else 365} days recency docs for {query}'
            url = 'https://example.com/hiring-burst'
        return [{"url": url, "title": url, "text": text}]

    def fake_invoke_structured_with_fallback(*, messages, schema, log_label, providers, thinking):
        nonlocal saw_thinking_override
        saw_thinking_override = thinking
        return AccountList(accounts=[_deterministic_account('Foo Inc', '')])

    def fake_linkedin_get_company(url, config=None):
        return {"name": 'Foo Inc', "website": 'https://foo.com', "domain": 'foo.com', "logo": 'https://foo.com/logo.png'}

    discovery.search_and_scrape = fake_search_and_scrape
    discovery.invoke_structured_with_fallback = fake_invoke_structured_with_fallback
    discovery.linkedin.get_company = fake_linkedin_get_company
    discovery.instagram.get_profile = lambda url, config=None: {"url": url, "name": 'Foo Inc'}
    discovery.tiktok.get_profile = lambda url, config=None: {"url": url, "name": 'Foo Inc'}
    discovery.x.get_profile = lambda url, config=None: {"url": url, "name": 'Foo Inc'}

    old_discovery_fast = discovery._FAST_DISCOVERY
    old_env = os.environ.get('ACCOUNT_DISCOVERY_FAST')
    env_strict_old = os.environ.pop('ACCOUNT_DISCOVERY_STRICT_REACHABILITY', None)
    discovery._FAST_DISCOVERY = True
    os.environ['ACCOUNT_DISCOVERY_FAST'] = '1'
    try:
        state: IcpSessionState = {
            'icp_data': ICP(
                product_name='Fixture',
                buyer_type='b2b',
                industries=['software'],
                geo=['Kenya'],
                buyer_titles=['CTO'],
                buyer_personas=[],
                target_channels=[],
                messaging_angles=[],
                exclusions=[],
                pain_signals=['expensive retraining'],
                intent_keywords=['database'],
                competitor_leads=[],
            ),
            'offer_type': 'service',
            'offer_name': 'Fixture',
            'icp_findings': 'fixture findings',
            'icp_understanding': 'fixture understanding',
            'icp_complete': True,
        }
        result = run_account_discovery(state)
        accounts = result.get('accounts')
        assert accounts is not None, 'no accounts returned'
        print(f'deterministic run kept {len(accounts.accounts)} account(s):')
        for acc in accounts.accounts:
            t = acc.trigger_event
            print(f' - {acc.name} | website={acc.website} | socials={acc.socials} | contacts={[c.model_dump() for c in acc.key_contacts]} | trigger={t.signal_type}:{t.event}')
        assert isinstance(saw_thinking_override, bool), 'extract LLM never invoked'
        assert any(acc.socials for acc in accounts.accounts), 'fast mode should have populated company socials'
        assert all(acc.website for acc in accounts.accounts), 'fixture path should enrich website'
    finally:
        discovery.search_and_scrape = original_search
        discovery.invoke_structured_with_fallback = original_invoke
        discovery.linkedin.get_company = original_linkedin_get_company
        discovery.instagram.get_profile = original_instagram_get_profile
        discovery.tiktok.get_profile = original_tiktok_get_profile
        discovery.x.get_profile = original_x_get_profile
        discovery._FAST_DISCOVERY = old_discovery_fast
        if old_env is not None:
            os.environ['ACCOUNT_DISCOVERY_FAST'] = old_env
        else:
            os.environ.pop('ACCOUNT_DISCOVERY_FAST', None)
        if env_strict_old is not None:
            os.environ['ACCOUNT_DISCOVERY_STRICT_REACHABILITY'] = env_strict_old
        else:
            os.environ.pop('ACCOUNT_DISCOVERY_STRICT_REACHABILITY', None)

    # Strict reachability drop check: with no socials/emails/LinkedIn trigger,
    # strict mode must drop even a website-present company.
    bad = _deterministic_account('BadCo', 'bad.com')
    bad.website = 'https://bad.com'
    bad.domain = 'bad.com'
    bad.trigger_event = TriggerEvent(event='saw a thing', signal_type='hiring_post', source='https://bad.com/news')
    bad.sources = [SourceRecord(title='n', url='https://bad.com/news')]
    os.environ['ACCOUNT_DISCOVERY_STRICT_REACHABILITY'] = '1'
    try:
        result_bad = discovery.verify_accounts({'accounts': AccountList(accounts=[bad])})
        assert len(result_bad['accounts'].accounts) == 0, 'strict mode should drop zero-reachability accounts'
        print(' strict reachability gate dropped zero-channel account OK')
    finally:
        os.environ.pop('ACCOUNT_DISCOVERY_STRICT_REACHABILITY', None)


def main():
    run_deterministic_checks()

    run_live = os.environ.get("ACCOUNT_DISCOVERY_LIVE", "").strip().lower() in ("1", "true", "yes")
    if not run_live:
        print("\nSkipping live LLM/Exa integration run; set ACCOUNT_DISCOVERY_LIVE=1 to include it.")
        return

    # Use the real product branch from the build_icp harness so we have a populated
    # market_data/competition_data inside icp_context.
    for branch_name in ("service_b2b",):
        base = BRANCHES[branch_name]
        print(f"\n### Branch: {branch_name} - {base.get('offer_name')} ###")
        fast = os.environ.get("ACCOUNT_DISCOVERY_FAST", "").strip().lower() in ("1", "true", "yes")

        # 1️⃣ Run the ICP stage to get real icp_data
        if fast:
            icp_data = ICP(
                product_name=base.get("offer_name"),
                buyer_type=base.get("buyer_type") or "b2b",
                industries=["software", "consulting"],
                company_sizes=["10-200"],
                geo=base.get("target_market") or ["Kenya"],
                buyer_titles=["CTO", "Head of Engineering"],
                pain_signals=["expensive retraining", "GPU dependence"],
                intent_keywords=["database", "AI"],
                competitor_leads=[],
            )
            icp_result = {"icp_data": icp_data}
            print("  FAST MODE: skipping build_icp_graph; seeded minimal ICP.")
        else:
            icp_graph = build_icp_graph()
            icp_result = icp_graph.invoke(base)
            icp_data = icp_result.get("icp_data")
            print(f"  icp produced by build_icp_graph: {icp_data.model_dump_json(indent=2)[:300]}")

        # 2️⃣ Build account discovery state using that ICP
        state: IcpSessionState = {
            **base,
            "icp_data": icp_data,
            "icp_findings": icp_result.get("icp_findings") or "",
            "icp_understanding": icp_result.get("icp_understanding") or "",
            "icp_complete": icp_result.get("icp_complete") is True,
        }

        result = run_account_discovery(state)
        accounts = result.get("accounts")
        print("Account list length:", len(accounts.accounts) if accounts else 0)
        if accounts:
            for acc in accounts.accounts[:10]:
                t = acc.trigger_event
                t_str = f"{t.signal_type}: {t.event}" if t else "none"
                print(f" - {acc.name} | {acc.website} | trigger={t_str}")
            print("\nAccount list JSON:")
            print(accounts.model_dump_json(indent=2))

            # --- Accuracy rubric -------------------------------------------------
            docs = result.get("account_discovery_docs") or []
            doc_urls = {d.get("url") for d in docs}
            total = max(len(accounts.accounts), 1)
            with_trigger_source = sum(
                1 for a in accounts.accounts
                if a.trigger_event and a.trigger_event.source in doc_urls
            )
            with_geo = sum(1 for a in accounts.accounts if a.geo)
            domains = [a.domain or a.website or a.name for a in accounts.accounts]
            dupes = len(domains) - len(set(d.strip().lower() for d in domains))
            print("\n--- Accuracy rubric ---")
            print(f"trigger source verifiable in docs : {with_trigger_source}/{total}")
            print(f"geo present                       : {with_geo}/{total}")
            print(f"duplicate domains                 : {dupes}")
            print(f"docs retrieved                    : {len(docs)}")
            print(f"queries used                      : {len(result.get('account_discovery_queries') or [])}")


if __name__ == "__main__":
    main()
