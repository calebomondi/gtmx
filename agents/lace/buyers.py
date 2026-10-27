"""Who buys from the startup: what a Lace must know before it looks for
customers. A thin site ("we build the future with AI & Web3") says what a
startup does but not who pays for it, and a search run on a guess comes back
with whoever matched the guess. So when the Lace knows little about its
buyers, it asks the founder first, in a short form, and its customer search
waits for the answer."""

from agents.schemas.lace import Fact
from agents.schemas.lace_ui import FormBlock, FormField, new_block_id

# Facts about who buys, and how many it takes to search on them.
BUYER_TOPICS = ("customers", "icp")
ENOUGH_BUYER_FACTS = 2

# Said instead of open questions in the opening message when the form asks them.
ASKED_IN_FORM = ("(Who pays us, a few past customers and where they are: these are asked in a short form under "
                 "your message. Say in one line that a few quick answers will point your searches at the right "
                 "customers; don't ask them in your text.)")

NOT_YET = ("We don't know who buys from us yet, so a customer search would be a guess. Ask the founder first with "
           "ask_form (who pays us, 1-3 past customers, where they are), record what they say with record_fact "
           "(topic customers), then search.")


def knows_buyers(facts: list[Fact]) -> bool:
    """Whether enough is known about who buys to search for more of them."""
    return sum(f.topic in BUYER_TOPICS for f in facts) >= ENOUGH_BUYER_FACTS


def buyer_form() -> FormBlock:
    """The questions that point a customer search at the right companies."""
    return FormBlock(id=new_block_id(), question="Who should I look for?", submit="Find them", fields=[
        FormField(name="who_pays", label="Who pays us for this? (a kind of company or person)", kind="long_text"),
        FormField(name="past_customers", label="1 to 3 past customers, if any", required=False),
        FormField(name="where", label="Where are they? (countries or cities)", required=False),
    ])
