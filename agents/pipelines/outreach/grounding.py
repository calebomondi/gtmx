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


def unsupported_numbers(text: str, sources: str) -> list[str]:
    """Quantities in `text` that appear in none of the sources."""
    known = _norm(sources)
    found = []
    for match in _QUANTITY.finditer(text):
        token = match.group(0).strip().rstrip(".,")
        digits = re.sub(r"\D", "", token)
        if not digits or _LOGISTICS.match(token) or _DURATION_AFTER.match(text[match.end():]):
            continue
        if len(digits) < 2 and not re.search(r"[%x×$€£₦]|million|billion|thousand|percent", token, re.I):
            continue  # "one call", "3 short paragraphs"
        if _norm(token) not in known and token not in found:
            found.append(token)
    return found


def problems(text: str, sources: str) -> list[str]:
    """Rewrite instructions for every grounding failure in `text`."""
    out = [f'Remove "{m}"' for m in dict.fromkeys(m.group(0) for m in BANNED.finditer(text))]
    out += [f'"{n}" appears in none of your sources: remove it or use a figure the research states'
            for n in unsupported_numbers(text, sources)]
    out += [f'"{m}" claims results or customers the research doesn\'t establish: cut it or name real proof'
            for m in dict.fromkeys(m.group(0) for m in _GENERIC_PROOF.finditer(text))]
    return out
