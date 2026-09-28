from datetime import date, timedelta

from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage, HumanMessage

from agents.llm.main import invoke_structured_with_fallback
from agents.states import (
    AccountDiscoveryState,
    AccountDiscoveryQueries,
    AccountList,
    OfferGtmSection,
)
from agents.helpers import as_offer_snapshot, format_offer_material, icp_block, market_context_block, competition_context_block
from agents.sub_graphs.understand_product import _offer_type_for, join_context
from config import Config
from data_sources.scraping.exa import search_and_scrape


def _recency_cutoff(days: int) -> str:
    """ISO date (YYYY-MM-DD) for the oldest source the account search may use."""
    return (date.today() - timedelta(days=days)).isoformat()


def _reach_emphasis(icp) -> str:
    """Tell the account search/extraction how to treat reachable venues vs companies."""
    buyer_type = (icp.buyer_type or "b2b").lower()
    if buyer_type == "b2c":
        return (
            "This is a CONSUMER offer. The targets are mostly NOT companies — they are the "
            "channels/communities/events/creators/platforms where the ICP congregates (from "
            "`target_channels` and `event_focus`): LinkedIn/Facebook groups, subreddits, Discords, "
            "newsletters, creators, marketplaces, and events/summits/conferences with their "
            "organisers. Find those venues as first-class targets, alongside any direct businesses."
        )
    if buyer_type == "both":
        return (
            "This offer serves BOTH companies and consumers. Find the company targets from the "
            "firmographics AND the consumer-reach venues (channels/communities/events/creators) "
            "from `target_channels` and `event_focus`. Both are first-class targets."
        )
    return (
        "This is a B2B offer. Find real COMPANIES that fit the firmographics; only surface a "
        "channel/event if it clearly concentrates multiple target accounts."
    )


def _trigger_line() -> str:
    return (
        "TRIGGER_SIGNAL_TYPES: hiring_post, competitor_review_mention, payment_integration, "
        "social_growth_spike, community_growth_spike, product_listing, funding_round, event_upcoming."
    )


account_search_instructions = """
You are an outbound researcher building a target list for the following {offer_noun}.

Use this Ideal Customer Profile (ICP) to find REAL targets the {offer_noun} could reach.

{icp}

REACH EMPHASIS
{reach_emphasis}

GOAL
Generate 4-8 web-search queries that surface concrete targets. Vary the query types:
- ICP intent-keyword × geo × industry queries (e.g. "best <tool> for <industry> in <geo> hiring 2026")
- Competitor customer/pain queries (people evaluating or complaining about the named competitors)
- Trigger-signal queries (hiring posts, funding rounds, growth, payment integrations)
- For consumer offers: channel/community queries (groups, subreddits, Discords, newsletters,
  creators, marketplaces for the ICP personas) AND event queries (events/summits/conferences/
  meetups matching the `event_focus`, e.g. "<topic> summit 2025 <geo> tickets/organizer").

RULES
1. Bias queries toward RECENT, current activity (recency is enforced on the search too).
2. Include the target geographies where known.
3. NEVER invent names in the queries — let the search surface them.
4. Keep to 4-8 queries.
"""


def search_web(state: AccountDiscoveryState) -> dict:
    """Generate 4-8 ICP-grounded queries, run them recency-gated through Exa,
    dedupe by URL, and append the results as formatted context for extraction."""
    icp = state.get("icp")
    if not icp:
        print("⚠️ No ICP to search on.")
        return {"context": []}

    specialist = state["specialist"]
    offer = as_offer_snapshot(state.get("offer_snapshot"))
    offer_noun = _offer_type_for(state)
    material = format_offer_material(offer, state.get("scraped_content"), offer_noun)
    markets = ", ".join(offer.target_geo or []) or "not specified"
    start_published_date = _recency_cutoff(Config().market_recency_days)

    print("Creating account-discovery queries ...")
    queries = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=account_search_instructions.format(
                offer_noun=offer_noun,
                icp=icp_block(icp),
                reach_emphasis=_reach_emphasis(icp),
            )),
            HumanMessage(content=f"SPECIALIST'S LENS: {specialist.distinct_lens or specialist.focus}\nTARGET MARKETS: {markets}\n\n{offer_noun.upper()} MATERIAL:\n{material or 'None provided.'}"),
        ],
        schema=AccountDiscoveryQueries,
        log_label="search_web:account_discovery_queries",
        thinking=False,
    )
    print(f"✅ {len(queries.queries)} queries generated:\n{chr(10).join(' - ' + q for q in queries.queries)}")

    print(f"Searching web (published after {start_published_date}) ...")
    docs = []
    seen = set()
    for q in queries.queries:
        if not q:
            continue
        results = search_and_scrape(
            q, Config(), num_results=3, start_published_date=start_published_date
        )
        for d in results:
            if d["url"] not in seen:
                seen.add(d["url"])
                docs.append(d)
        if not results:
            print(f"  -> empty: {q}")
    print(f"{"✅ Search complete" if docs else "❌ Search failed"} ({len(docs)} unique docs)")

    formatted_search_docs = "\n\n---\n\n".join(
        [
            f'<Document href="{doc["url"]}"/>\n{doc["title"]}\n-----\n{doc["text"]}\n</Document>'
            for doc in docs
        ]
    )
    return {"context": [formatted_search_docs]}


account_extraction_instructions = """
You are an outbound researcher. From the CURRENT web research below, extract the targets (the
{offer_noun}'s target accounts AND, for consumer offers, its reachable channels/communities/events/
creators/platforms) worth reaching out to for this {offer_noun}.

The {offer_noun}'s OWN material (the block labelled "{offer_noun}'s own material") is authoritative.

ICP:
{icp}

REACH EMPHASIS
{reach_emphasis}

Research context:
{context}

Rules:

- targets: Find between 4 and 8 REAL targets that fit the ICP. Each must be grounded in the
  research context and MUST have a `trigger_event` — a current, verifiable signal observed in the
  sources that makes outreach timely now (see TRIGGER_SIGNAL_TYPES below). If a candidate has no
  current trigger, exclude it. Never invent a target, a trigger, or a source.

  {trigger_line}

  For each target:
  * name: real name as it appears in the sources.
  * account_type: "company", or for consumer-reach venues "community" / "event" / "creator" /
    "platform" — set it to what the target actually is.
  * website/domain, industry, size, geo: only what the sources actually state; otherwise null.
  * platform: for non-company targets the platform it lives on (LinkedIn group, Substack, YouTube,
    Discord, subreddit name, marketplace), if stated.
  * venue / event_date: for events the city/venue and date/period, if stated.
  * member_size: for communities/creators the audience/member size, if stated.
  * For events/communities: organisers/hosts/admin go in key_contacts.
  * key_contacts: the people to reach out to — name/title/LinkedIn/email ONLY when present in the
    sources. Never fabricate a person or their contact details.
  * pain_signals / hiring_signals: observed signals matching the ICP.
  * sources: the URLs that prove the target exists and the trigger is current.
  * score (0-1) with a short score_breakdown using the rubric: ICP fit .30, reach/geo fit .20,
    pain fit .20, trigger strength .15, defensibility .15.
  * why_selected: exactly 5 reasons this target fits the ICP.
  * why_reach_out: exactly 5 outreach angles for the target's opening, grounded in the observed
    signals.

- Hard constraints from the ICP must hold: exclude `exclusions`, keep to the ICP's geographies and,
  for companies, `company_sizes`.

OUTPUT
Return only the structured fields — no commentary.
"""


def extract_accounts(state: AccountDiscoveryState) -> dict:
    """Extract the structured target list (companies and/or reachable venues)
    from the ICP + gathered web docs, scoped through the GTM specialist's lens."""
    context = join_context(state.get("context"))
    icp = state.get("icp")
    specialist = state["specialist"]
    offer = as_offer_snapshot(state.get("offer_snapshot"))
    offer_noun = _offer_type_for(state)

    print("Extracting targets ...")
    accounts = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=account_extraction_instructions.format(
                offer_noun=offer_noun,
                icp=icp_block(icp),
                reach_emphasis=_reach_emphasis(icp),
                context=context or "No research context available.",
                trigger_line=_trigger_line(),
            )),
            HumanMessage(
                content=(
                    f"SPECIALIST'S LENS: {specialist.distinct_lens or specialist.focus}\n\n"
                    f"{offer_noun.upper()} OWN MATERIAL:\n{format_offer_material(offer, state.get('scraped_content'), offer_noun) or 'None provided.'}"
                )
            ),
        ],
        schema=AccountList,
        log_label="extract_accounts",
        thinking=False,
    )
    print(f"✅ Targets extracted ({len(accounts.accounts)}):")
    for a in accounts.accounts:
        t = a.trigger_event.signal_type if a.trigger_event else "none"
        print(f"   - {a.name} [{a.account_type or 'company'} | {t}] {a.geo or '?'} score={a.score}")
    return {"accounts": accounts}


def verify_accounts(state: AccountDiscoveryState) -> dict:
    """Hard-constraint pass: dedupe by domain (or platform::name for venues),
    drop targets with no current trigger event, cap at 8. Warn (don't invent)
    when fewer than 4 survive."""
    accounts = state.get("accounts")
    if not accounts:
        return {"accounts": AccountList(accounts=[])}

    kept, seen = [], set()
    for acc in accounts.accounts:
        if acc.trigger_event is None:
            print(f"❌ Dropping '{acc.name}' — no current trigger_event.")
            continue
        if acc.account_type and acc.account_type != "company":
            key = f"{acc.platform or acc.account_type}::{acc.name}".strip().lower()
        else:
            key = (acc.domain or acc.website or acc.name).strip().lower()
        if key in seen:
            print(f"❌ Dropping duplicate '{acc.name}' (already kept).")
            continue
        seen.add(key)
        kept.append(acc)

    kept = kept[:8]
    verified = AccountList(accounts=kept)
    print(f"✅ Verified targets: {len(kept)} (dropped {len(accounts.accounts) - len(kept)})")
    if len(kept) < 4:
        print("⚠️ Fewer than 4 defensible targets — keeping the defensible set, not inventing more.")
    return {"accounts": verified}


gtm_section_writer_instructions = """You are an expert technical writer and GTM strategist.

Your task is to create a short, easily digestible section of a report that lays out the
{offer_noun}'s ideal customer profile and the targets found for outreach — grounded in the
{offer_noun}'s own material and CURRENT sources.

The context contains the {offer_noun}'s OWN MATERIAL (the document labelled "{offer_noun}'s own
material" — authoritative facts about the {offer_noun}: what it is, who it is for, its features)
followed by documents about the TARGET research the {offer_noun} can reach (real companies and,
for consumer offers, channels/communities/events/creators — their triggers, pain/hiring signals).

1. Analyze the content of the source documents:
- The name of each source document is at the start of the document, with the <Document tag.

2. Create a report structure using markdown formatting:
- Use ## for the section title
- Use ### for sub-section headers

3. Write the report following this structure:
a. Title (## header)
b. Summary (### header)
c. Sources (### header)

4. Make your title engaging based upon the focus area of the {offer_noun} gtm specialist:
{focus}

5. For the summary section:
- Open with the Ideal Customer Profile: who the {offer_noun} is for (industries, sizes, geos,
  buyer titles/personas, and — for consumer offers — the channels/communities/events where the
  audience congregates)
- List the top 4-8 targets found, and for each: why it fits the ICP, the current trigger that
  makes now the right time to reach out, and who to contact if a contact is known
- Use what the account-discovery research actually found to make the list concrete —
  the {offer_noun} must be the subject, the targets the framing
- Also return `go_to_market_understanding` as a brief standalone synthesis of the go-to-market
  story — who to target, why now, and the opening angle;
  target 40 words and never exceed 50 words
- Ground everything in the CURRENT research; flag anything that is an estimate
- Name only real targets and contacts found in the sources
- Create a numbered list of source documents, as you use them
- Do not mention the names of interviewers or experts
- Aim for approximately {word_count} words maximum for the summary, excluding the title and sources

6. In the Sources section:
- Include all sources used in your report
- Provide full links to relevant websites or specific document paths
- Separate each source by a newline. Use two spaces at the end of each line to create a newline in Markdown.
- It will look like:

### Sources
[1] Link or Document name
[2] Link or Document name

7. Be sure to combine sources. For example this is not correct:

[3] https://example.com/1
[4] https://example.com/1

There should be no redundant sources. It should simply be:

[3] https://example.com/1

8. Final review:
- Ensure the report follows the required structure
- Include no preamble before the title of the report
- Check that the section names only real accounts and contacts and stays grounded in the sources
- Check that all guidelines have been followed"""


def write_section(state: AccountDiscoveryState) -> dict:
    """Node to write the GTM / account-discovery report section."""
    context = join_context(state.get("context"))
    specialist = state["specialist"]
    icp = state.get("icp")
    accounts = state.get("accounts")
    offer = as_offer_snapshot(state.get("offer_snapshot"))
    offer_noun = _offer_type_for(state)
    material = format_offer_material(offer, state.get("scraped_content"), offer_noun)

    system_message = gtm_section_writer_instructions.format(
        offer_noun=offer_noun,
        focus=specialist.focus,
        word_count=state.get("section_word_count", 500),
    )
    print("Writing GTM section ...")
    section = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=system_message),
            HumanMessage(content=(
                "Write the section from what the account-discovery research actually found, the "
                f"{offer_noun}'s own material, the ICP, and the verified target accounts.\n\n"
                f"SPECIALIST'S LENS: {specialist.distinct_lens or specialist.focus}\n\n"
                f"{offer_noun.upper()} MATERIAL:\n{material or 'None provided.'}\n\n"
                f"MARKET CONTEXT:\n{market_context_block(state.get('market_data'))}\n\n"
                f"COMPETITION CONTEXT:\n{competition_context_block(state.get('competition_data'))}\n\n"
                f"ICP:\n{icp_block(icp)}\n\n"
                f"VERIFIED TARGETS:\n{accounts.model_dump_json(indent=2, exclude_none=True) if accounts else 'None found.'}\n\n"
                f"ACCOUNT RESEARCH SOURCES:\n{context}"
            )),
        ],
        schema=OfferGtmSection,
        log_label="write_gtm_section",
    )
    print(f"{"✅ GTM section written" if section else "❌ GTM section not written!"}")
    return {
        "sections": [section.section],
        "go_to_market_understanding": section.go_to_market_understanding,
        "gtm_complete": True,
    }


def build_account_discovery_graph(checkpointer: bool = True):
    """Build the account-discovery pipeline: given the ICP determined by the
    determine_icp subgraph, search for target accounts / consumer-reach channels
    + events (recency-gated), extract them with trigger events, validate, and
    write the GTM section.

    Compiled with a checkpointer by default so an interactive driver can resume
    interrupts; pass checkpointer=False when embedding as a subgraph node."""

    builder = StateGraph(AccountDiscoveryState)

    # -- Nodes --
    builder.add_node("search_web", search_web)
    builder.add_node("extract_accounts", extract_accounts)
    builder.add_node("verify_accounts", verify_accounts)
    builder.add_node("write_section", write_section)
    # -- Edges --
    builder.add_edge(START, "search_web")
    builder.add_edge("search_web", "extract_accounts")
    builder.add_edge("extract_accounts", "verify_accounts")
    builder.add_edge("verify_accounts", "write_section")
    builder.add_edge("write_section", END)

    # -- Compile --
    if checkpointer:
        memory_saver = MemorySaver()
        return builder.compile(checkpointer=memory_saver)
    return builder.compile()