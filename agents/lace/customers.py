"""Learning from the startup's real customers: read each one's own site and
say what it is (CustomerTraits), as a sourced fact the ideal customer profile
and lookalike searches build on. A customer whose site can't be read is
skipped, never guessed at."""

from collections.abc import Callable, Sequence

from langchain_core.messages import HumanMessage, SystemMessage

from agents.context_budget import _truncate_to_tokens
from agents.llm.main import cheap_providers, invoke_structured_with_fallback
from agents.schemas.icp import CustomerTraits
from agents.schemas.lace import NewFact
from config import Settings
from data_sources.scraping import firecrawl

# How much of a customer's home page the reader sees.
PAGE_TOKENS = 2_000

Read = Callable[[str, Settings], str]
Describe = Callable[[Sequence], CustomerTraits]

_PROMPT = """This is the website of {name}, a customer of {startup}. Say what
{name} is, only from the page: what it does, its industry, its size (staff,
sites, branches) and where it operates. Leave a field empty when the page
doesn't say; never guess.

PAGE ({url})
{page}"""


def _default_read(url: str, cfg: Settings) -> str:
    return firecrawl.scrape_page(url, cfg).markdown


def _default_describe(messages: Sequence) -> CustomerTraits:
    return invoke_structured_with_fallback(messages, CustomerTraits, providers=cheap_providers(),
                                           log_label="lace:customer_traits")


def describe_customer(name: str, website: str, startup: str, cfg: Settings, read: Read = _default_read,
                      describe: Describe = _default_describe) -> CustomerTraits | None:
    """What the customer is, from its site; None when the site can't be read
    or says nothing useful. Raises nothing for an unreadable site."""
    try:
        page = read(website, cfg)
    except firecrawl.FirecrawlError:
        return None
    if not page.strip():
        return None
    traits = describe([SystemMessage(content=_PROMPT.format(name=name, startup=startup, url=website,
                                                            page=_truncate_to_tokens(page, PAGE_TOKENS))),
                       HumanMessage(content="Describe the customer.")])
    return traits if traits.what_they_do.strip() else None


def customer_fact(name: str, website: str, traits: CustomerTraits) -> NewFact:
    """The customer, as one sourced fact about who buys from the startup."""
    details = ", ".join(d for d in (traits.industry, traits.size, traits.location) if d.strip())
    what = traits.what_they_do.strip().rstrip(".")
    claim = f"Customer {name}: {what}" + (f" ({details})" if details else "") + "."
    return NewFact(topic="customers", claim=claim, source_url=website, confidence="medium", origin="research")
