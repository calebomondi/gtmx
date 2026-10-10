"""
Create Virtual Specialists
"""

from typing import TypedDict, List, Optional, Literal
from pydantic import Field

from langgraph.graph import START, END, StateGraph
from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm.main import invoke_structured_with_fallback
from agents.schemas.research import Perspectives, Specialist
from agents.schemas.sessions import OfferSessionState


class OfferState(TypedDict):
    offer_type: Optional[Literal["product", "service"]] = None
    offer_name: str = Field(description="")
    offer_description: str = Field(description="")
    target_market: List[str] = Field(description="")
    specialists: List[Specialist] = Field(description="")
    specialist_generation_complete: bool = Field(default=False, description="")


specialist_team_instructions = """
You are tasked with creating FOUR AI specialist personas. Each specialist will focus on their own domains as follows;

1. product/service — deep expertise in the product/service domain space  -> domain: {domain_self}
2. market — expertise in the market and customer segments for the product/service in this category
   (who buys, demand, buyer segments, and pricing norms in the target markets)  -> domain: "market"
3. competition — expertise in this product/service category's competitive landscape
   (who competes, how they position, and where their customers hurt)  -> domain: "competition"
4. go-to-market — expertise in go-to-market strategy for product/service in this category
   (channels, ICP, entry per geography, and how the offer wins)  -> domain: "gtm"

Follow these instructions carefully:

1. First, review the product/service name, description and target geo-location:
- name          : {offer_name}
- type          : {offer_type}
- description   : {offer_desc}
- target market : {offer_geo}
        
2. Assign one specialist to each domain, and set that specialist's `domain` field
   to exactly the value shown beside their slot above. That field is required and
   is how a later stage selects the right specialist out of the team, so it must
   match. Do not paraphrase it, and do not leave it empty.

CONSTRUCTION RULES

- These are fictional persona constructs for this session — do not name or
  model them on any real, identifiable person.
- Specialists are domain experts, not insiders: none of them built or shaped
  this product/service. Their perspective comes from the product/service description and their
  category/domain expertise alone.
- Each specialist’s role, affiliation, and description must reflect the supplied
  product/service context: the role name should match their domain and the
  offer description, the affiliation should be plausible for that kind of role,
  and the description should explain how their expertise applies to the
  described offering.
- Specialist names should correspond to the user's **target geographies**, which
  are typically specified as country/countries (not broad regions). Use names that
  plausibly come from the exact countries listed; if multiple countries are given,
  choose names from one of those countries rather than a generic global label.
  Be creative and keep names fictitious, never a real, identifiable person.

"""

def create_specialists_team(state: OfferState):
    """Create Specialists Team"""

    offer_type = state["offer_type"]
    name = state["offer_name"]
    descp = state["offer_description"]
    market = state["target_market"]

    system_message = specialist_team_instructions.format(
        offer_type = offer_type,
        offer_name = name,
        offer_desc = descp,
        offer_geo = market,
        # The offer's own expert is a "product" or a "service" depending on what
        # was discovered, because Specialist.domain is a closed literal and the
        # downstream offer-research stage selects this specialist by that value.
        domain_self = "service" if offer_type == "service" else "product",
    )

    specialists = invoke_structured_with_fallback(
        messages=[
            SystemMessage(content=system_message),
            HumanMessage(content="Generate the set of specialists")
        ],
        schema=Perspectives,
        log_label="Create Specialists"
    )

    return {
        "specialists": specialists.specialists,
        "specialist_generation_complete": True
    }

def build_specialist_graph():
    builder = StateGraph(OfferSessionState)

    # -- Nodes --
    builder.add_node("create_specialist_team", create_specialists_team)
    # -- Edges --
    builder.add_edge(START, "create_specialist_team")
    builder.add_edge("create_specialist_team", END)

    return builder.compile()