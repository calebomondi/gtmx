from __future__ import annotations

import re

# Acronyms preserved exactly as-written when normalized, so "api tool" and
# "API tool" both resolve to "API Tool" (and therefore the same name_key).
# Key = uppercased word, value = canonical casing.
_ACRONYMS = {
    "API": "API",
    "AI": "AI",
    "B2B": "B2B",
    "B2C": "B2C",
    "CEO": "CEO",
    "CFO": "CFO",
    "CLI": "CLI",
    "CMO": "CMO",
    "COO": "COO",
    "CRM": "CRM",
    "CTO": "CTO",
    "GTM": "GTM",
    "ICP": "ICP",
    "KPI": "KPI",
    "MVP": "MVP",
    "OKR": "OKR",
    "POC": "POC",
    "PRD": "PRD",
    "ROI": "ROI",
    "SAAS": "SaaS",
    "SDK": "SDK",
    "SDR": "SDR",
    "SEO": "SEO",
    "SMB": "SMB",
    "URL": "URL",
}


def title_case(name: str | None) -> str:
    """Normalize a user-supplied name to Title Case for storage.

    Every word starts with an uppercase letter and the remainder is
    lowercased; known acronyms are kept uppercase. Returns "" for empty input.

    Examples:
        "acme corp"   -> "Acme Corp"
        "GTMX Analyst"-> "Gtmx Analyst"
        "api tool"    -> "API Tool"
        "b2b saas crm"-> "B2B SaaS CRM"
    """
    text = (name or "").strip()
    if not text:
        return ""
    parts = re.split(r"\s+", text)
    result: list[str] = []
    for part in parts:
        if not part:
            continue
        canonical = _ACRONYMS.get(part.upper())
        if canonical:
            result.append(canonical)
        else:
            result.append(part[:1].upper() + part[1:].lower())
    return " ".join(result).strip()