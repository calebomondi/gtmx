"""An in-memory Lace store and a scripted model, for the offline Lace tests."""

import itertools
from datetime import datetime, timezone

from langchain_core.messages import AIMessage

from agents.schemas.lace import Fact, LaceProfile, NewFact, SourcePage


class MemoryStore:
    def __init__(self, facts: list[Fact] | None = None):
        self._facts = list(facts or [])
        self.superseded: set[str] = set()
        self.sources: dict[str, SourcePage] = {}
        self._ids = itertools.count(len(self._facts) + 1)
        self.startup_name: str | None = "Acme"
        self.website = "https://acme.test"

    async def profile(self) -> LaceProfile:
        return LaceProfile(name="Ada", website=self.website, startup_name=self.startup_name)

    async def set_startup_name(self, name: str) -> None:
        self.startup_name = name

    async def facts(self, topic=None, limit=50) -> list[Fact]:
        live = [f for f in reversed(self._facts) if f.id not in self.superseded]
        return [f for f in live if topic is None or f.topic == topic][:limit]

    async def record_fact(self, fact: NewFact) -> Fact:
        if fact.replaces_id is not None:
            if fact.replaces_id not in {f.id for f in self._facts}:
                raise KeyError(fact.replaces_id)
            self.superseded.add(fact.replaces_id)
        saved = Fact(**fact.model_dump(), id=f"f{next(self._ids)}", recorded_at=datetime.now(timezone.utc))
        self._facts.append(saved)
        return saved

    async def save_source(self, page: SourcePage) -> None:
        self.sources[page.url] = page


def make_fact(id: str, claim: str, topic="offer", confidence="high") -> Fact:
    return Fact(id=id, topic=topic, claim=claim, source_url="https://acme.test",
                confidence=confidence, recorded_at=datetime.now(timezone.utc))


class ScriptedModel:
    """Replays AIMessages in order and records what it was sent."""

    def __init__(self, *replies: AIMessage):
        self.replies = list(replies)
        self.calls: list[tuple[list, list]] = []

    def __call__(self, messages, tools, sink=None):
        self.calls.append((list(messages), list(tools)))
        reply = self.replies.pop(0)
        if sink is not None and reply.content:
            for word in str(reply.content).split(" "):
                sink.token(word + " ")
        return reply


def call(name: str, args: dict, id: str = "c1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": id}])
