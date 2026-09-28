from langgraph.graph import START, END, StateGraph
from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm.main import invoke_structured_with_fallback
from agents.states import OfferSessionState, SpecialistTeam, DomainSpecialist
from agents.helpers import as_offer_snapshot


team_instructions = """
You are tasked with creating a four-person specialist team for this {offer}
{offer} name: {offer_name}
{offer} description: {offer_description}

OFFER SNAPSHOT
{offer_snapshot}

REGION ASSIGNMENT
Target markets for this {offer}: {target_geo}
If the target markets are empty or unspecified, use neutral global personas and
work in English — never invent a geography the offer doesn't target.

The team covers four domains:
1. product — deep expertise in the {offer} domain space, including how
   {offer}s in this category are expected to perform and the standards they are
   held to (category conventions, benchmarks, and what "good" looks like)
2. market — expertise in the market and customer segments for {offer} in this category
   (who buys, demand, buyer segments, and pricing norms in the target markets)
3. competition — expertise in this product/service category's competitive landscape
   (who competes, how they position, and where their customers hurt)
4. go-to-market — expertise in go-to-market strategy for {offer} in this category
   (channels, ICP, entry per geography, and how the offer wins)

CONSTRUCTION RULES
- Specialists are domain experts, not insiders: none of them built or shaped
  this {offer}. Their perspective comes from the {offer} description and their
  category/domain expertise alone.
- Harden each specialist in their domain:
  * `background`: ground it in the actual {offer} snapshot above — the offer
    description, target markets, problem it solves, and how it works. No
    generic template bios.
  * `region` and `language`: anchor ALL four specialists to the target markets
    listed in REGION ASSIGNMENT. Draw names, language, and cultural idiom from
    those markets' naming conventions — a market specialist for West Africa is
    not named "John Smith in English". Keep names fictitious, never a real,
    identifiable person.
  * `operating_context`: a plausible, clearly fictional track record showing
    where they've worked and who they've advised in those markets — describe
    their experience/lens, NOT findings they supposedly already have.
  * `distinct_lens`: the concrete angle each specialist brings to this session
    — product specialist benchmarks the offer against category standards,
    market specialist reads demand/buyers/pricing, competition specialist maps
    landscape and customer pain, GTM specialist scores channels, ICP, and
    per-geography entry.
  * `focus`: state what they intend to pin down with the team in this session,
    phrased around the {offer} facts above.
- Write all four as a coherent team — vary names, voices, and angles so
  they don't sound interchangeable, but keep them consistent with the
  same {offer} facts.
- These are fictional persona constructs for this session — do not name or
  model them on any real, identifiable person.
- Do not fabricate specific competitor names, market data, or pricing
  figures in the bios — describe each specialist's approach/lens, not
  findings they supposedly already have.
- If the {offer} description is too thin to ground specifics, keep each
  persona general to the stated category rather than inventing details.

OUTPUT
Return ONE specialist object only, with fields {{domain, name, role_title,
background, focus, region, language, operating_context, distinct_lens}}. No
commentary.
"""


# Domain -> SpecialistTeam field. The first slot is the offer's own domain
# expert: its `domain` is "service" when the offer is a service, else "product".
# The other three slots always carry their fixed domain value.
def _specialist_slots(offer_type: str):
    first = "service" if offer_type == "service" else "product"
    return [
        (first, "product_or_service_specialist"),
        ("market", "market_specialist"),
        ("competition", "competition_specialist"),
        ("gtm", "gtm_specialist"),
    ]

specialist_instructions = """
TARGET SPECIALIST
Create the {target_domain} specialist now. Set "domain" to "{target_domain}"
and fill every other field for exactly this one specialist.
"""


def _build_specialist(
    grounding: str,
    target_domain: str,
    team_field: str,
) -> DomainSpecialist:
    system_message = grounding + specialist_instructions.format(
        target_domain=target_domain,
    )
    for _ in range(3):
        specialist = invoke_structured_with_fallback(
            messages=[
                SystemMessage(content=system_message),
                HumanMessage(content=f"Create the {target_domain} specialist."),
            ],
            schema=DomainSpecialist,
            log_label=f"Create {target_domain} specialist",
        )
        if specialist is not None and specialist.domain == target_domain:
            return specialist
    raise RuntimeError(
        f"Failed to build the {target_domain} specialist after 3 attempts."
    )


def create_specialist_team(state: OfferSessionState) -> dict:
    """Assemble the four-person specialist team grounded on the offer snapshot.

    One specialist at a time — a single DomainSpecialist object is far more
    reliably produced by the model than the 4-field team wrapper.
    """
    offer_type = state.get("offer") or "product"
    offer = as_offer_snapshot(state.get("offer_snapshot"))
    target_geo = offer.target_geo or []

    grounding = team_instructions.format(
        offer=offer_type,
        offer_name=offer.offer_name,
        offer_description=offer.offer_description,
        offer_snapshot=offer.model_dump_json(indent=2, exclude_none=True),
        target_geo=", ".join(target_geo) if target_geo else "unspecified/global",
    )

    team = SpecialistTeam(
        **{
            team_field: _build_specialist(grounding, domain, team_field)
            for domain, team_field in _specialist_slots(offer_type)
        }
    )
    return {"specialist_team": team, "specilist_generation_complete": True}


def build_specialist_graph():
    builder = StateGraph(OfferSessionState)

    # -- Nodes --
    builder.add_node("create_specialist_team", create_specialist_team)
    # -- Edges --
    builder.add_edge(START, "create_specialist_team")
    builder.add_edge("create_specialist_team", END)

    return builder.compile()