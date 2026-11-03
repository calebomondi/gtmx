"""Public visitors (the waitlist, a Store's buyers) are rate limited per IP
without keeping the IP: only a salted hash of it is stored."""

import hashlib

from config import settings


def ip_hash(ip: str | None) -> str | None:
    return hashlib.sha256(f"{settings.waitlist_ip_salt}:{ip}".encode()).hexdigest() if ip else None
