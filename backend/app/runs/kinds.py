"""The kinds of agent run. One list, so caps, quotas and the executors can't
drift apart."""

from typing import Literal, get_args

RunKind = Literal[
    "discovery", "competitors", "accounts", "competitor_research", "chat", "outreach_drafts", "outreach_reply",
    "monitor",
]
RUN_KINDS: tuple[str, ...] = get_args(RunKind)
