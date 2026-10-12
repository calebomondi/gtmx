"""Mechanical grounding checks for anything the GTM specialist writes to a
prospect. A reviewer model reads a fluent draft as fine; these catch what it
misses: copy no good seller writes, numbers that appear in none of the
sources the writer was given, and claims of customers or results nobody
established. Each problem is phrased as an instruction for the rewrite.
"""

import re

# Copy a good seller never writes.
BANNED = re.compile(
    r"\b(synerg\w*|leverag\w*|revolutioni[sz]\w*|cutting[- ]edge|game[- ]chang\w*|enhanc\w*|"
    r"drive (?:further )?impact|impressive|hope (?:this|you)|came across|quick intro|"
    r"we(?:'re| are) aware|touch base|circle back|unlock\w*|empower\w*|seamless\w*)\b",
    re.I,
)

# Results or customers claimed in general terms: only real, named proof from
# the research may be cited, and a writer reaching for these has none.
_PEERS = (r"(?:companies|teams|banks|fintechs|processors|businesses|firms|clients|scale-?ups|start-?ups|"
          r"lenders|operators|organi[sz]ations|players|brands|retailers|manufacturers|labs)")
_GENERIC_PROOF = re.compile(
    r"\b(we(?:'ve| have| are|'re) (?:helped|helping|worked with|working with|supported|supporting)|"
    r"helped (?:similar|other|many|several)\b|"
    rf"(?:similar|other|many|leading)\s+(?:[a-z-]+\s+){{0,2}}{_PEERS}|"
    r"our (?:clients|customers) (?:see|saw|have|report|achieve)|customers like you|companies like yours)",
    re.I,
)

# A quantity: percentages, multipliers, money, and numbers with a scale word.
_QUANTITY = re.compile(
    # The rand sign only when it stands alone ("R 500"), never the r ending "for".
    r"(?:[$€£₦]|\bKES\s?|\bZAR\s?|(?<![A-Za-z])R\s?(?=\d))?\d[\d,.]*\s?(?:%|x\b|×|(?:k|m|bn)\b|"
    r"(?:thousand|million|billion|percent)\b)?",
    re.I,
)
# Meeting logistics, not claims: "15-minute call", "Tue 14 Oct", "10:00".
_LOGISTICS = re.compile(r"^\d{1,2}(?::\d{2})?$")
_DURATION_AFTER = re.compile(r"^\s?-?\s?(?:minute|min|hour|hr|day|week)s?\b", re.I)


def _norm(text: str) -> str:
    return re.sub(r"[\s,]", "", text.lower()).replace("×", "x").replace("percent", "%")


_SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9}
_MONEY_BEFORE = re.compile(r"[$€£₦]|\b(?:KES|ZAR|USD|NGN)\b|(?<![A-Za-z])R\s?\d", re.I)
_MONEY_AFTER = re.compile(r"^\s?(?:KES|ZAR|USD|NGN|dollars?|rand|naira|shillings?)\b", re.I)


def _amount(token: str, after: str) -> tuple[str, float] | None:
    """A quantity's kind and value, so '15k KES' and '15,000 KES' (or '$200M'
    and '$200 million') are the same claim. Money, percentages, multipliers
    and plain counts never match each other: '200 million API calls' is not
    the '$200M' a source states."""
    number = re.search(r"\d[\d,]*(?:\.\d+)?", token)
    if not number:
        return None
    try:
        value = float(number.group(0).replace(",", ""))
    except ValueError:
        return None
    scale = re.search(r"(k|m|bn|thousand|million|billion)\s*$", token, re.I)
    value *= _SCALE[scale.group(1).lower()] if scale else 1
    if re.search(r"%|percent", token, re.I):
        kind = "%"
    elif re.search(r"x$|×", token.strip(), re.I):
        kind = "x"
    elif _MONEY_BEFORE.search(token) or _MONEY_AFTER.match(after):
        kind = "money"
    else:
        kind = "n"
    return kind, round(value, 6)


def _amounts(text: str) -> set[tuple[str, float]]:
    found = set()
    for match in _QUANTITY.finditer(text):
        amount = _amount(match.group(0).strip().rstrip(".,"), text[match.end():match.end() + 12])
        if amount:
            found.add(amount)
    return found


def unsupported_numbers(text: str, sources: str) -> list[str]:
    """Quantities in `text` that appear in none of the sources."""
    known = _norm(sources)
    known_amounts = _amounts(sources)
    found = []
    for match in _QUANTITY.finditer(text):
        token = match.group(0).strip().rstrip(".,")
        digits = re.sub(r"\D", "", token)
        if not digits or _LOGISTICS.match(token) or _DURATION_AFTER.match(text[match.end():]):
            continue
        if len(digits) < 2 and not re.search(r"[%x×$€£₦]|million|billion|thousand|percent", token, re.I):
            continue  # "one call", "3 short paragraphs"
        if _norm(token) in known or _amount(token, text[match.end():match.end() + 12]) in known_amounts:
            continue
        if token not in found:
            found.append(token)
    return found


def problems(text: str, sources: str) -> list[str]:
    """Rewrite instructions for every grounding failure in `text`."""
    text = text.replace("\u2019", "'").replace("\u2018", "'")  # "we’re" reads as "we're"
    out = [f'Remove "{m}"' for m in dict.fromkeys(m.group(0) for m in BANNED.finditer(text))]
    out += [f'"{n}" appears in none of your sources: remove it or use a figure the research states'
            for n in unsupported_numbers(text, sources)]
    out += [f'"{m}" claims results or customers the research doesn\'t establish: cut it or name real proof'
            for m in dict.fromkeys(m.group(0) for m in _GENERIC_PROOF.finditer(text))]
    return out
