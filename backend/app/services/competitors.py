"""A competitor's or startup's website as one identity: the address to use,
and the host that dedups it."""

import re
from urllib.parse import urlparse




def normalize_website(website: str) -> str:
    """A bare host ("acme.com") means https://acme.com."""
    website = website.strip()
    if not re.match(r"^https?://", website, re.IGNORECASE):
        website = f"https://{website}"
    return website


def domain_key(website: str) -> str:
    """The host that identifies the firm behind a URL.

    The same rival is reachable at http://acme.com, https://www.acme.com/ and
    https://acme.com/about; deduping on the raw URL would file one company three
    times. Falls back to the lowercased input when there is no parseable host,
    so a malformed URL still yields a stable, non-empty key.
    """
    host = (urlparse(website).netloc or "").strip().lower()
    if not host:
        return website.strip().lower()
    host = host.split("@")[-1]  # drop any userinfo
    host = host.split(":")[0]  # drop the port
    return host.removeprefix("www.").rstrip(".")
