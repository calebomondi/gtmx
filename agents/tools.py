from langchain_core.tools import tool

from config import get_settings
from data_sources.scraping.exa import scrape_url as _scrape_url
from data_sources.scraping.exa import search_and_scrape as _search_and_scrape
from data_sources.parsing.documents import parse_document as _parse_document

cfg = get_settings()


@tool
def scrape_url(url: str) -> str:
    """Scrape a website URL and return clean text content.

    Use this ONLY for URLs the user explicitly provides (the product's own website
    or a link the user shares). NEVER scrape URLs found in search_web results.
    Returns the main text content of the page.
    """
    return _scrape_url(url, cfg)


@tool
def parse_document(file_path: str) -> str:
    """Parse a document file and return its text content.

    Supports PDF, DOCX, PPTX, TXT, and MD files.
    Use this when the user provides a document file path containing
    product information you need to analyze.
    """
    return _parse_document(file_path)


@tool
def search_web(query: str) -> str:
    """Search the web for product, market, competitor, pricing, or positioning information.

    Use this to research competitors, compare pricing, answer product/GTM questions, or any
    market topic. Returns search results with titles, URLs, and text snippets.
    """
    results = _search_and_scrape(query, cfg, num_results=3)
    if not results:
        return "No search results found."
    output = []
    for r in results:
        output.append(f"**{r['title']}**\n{r['url']}\n{r['text'][:500]}")
    return "\n\n".join(output)
