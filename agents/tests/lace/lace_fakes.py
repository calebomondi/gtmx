"""An in-memory Lace store and a scripted model, for the offline Lace tests."""

import itertools
from datetime import datetime, timezone

from langchain_core.messages import AIMessage

from agents.lace.store import JobRefused
from agents.schemas.lace import CompetitorSummary, ContactSummary, DocumentSummary, DraftSummary, Fact, ItemsChanged, NamedItem, Suggestions, LaceProfile, NewFact, SourcePage


class MemoryStore:
    def __init__(self, facts: list[Fact] | None = None):
        self._facts = list(facts or [])
        self.superseded: set[str] = set()
        self.sources: dict[str, SourcePage] = {}
        self.tracked: list[CompetitorSummary] = []
        self.drafted: list[DraftSummary] = []
        self.suggested = Suggestions()
        self.saved_icp = None
        self.targets: list = []
        self._ids = itertools.count(len(self._facts) + 1)
        self.startup_name: str | None = "Acme"
        self.proposed: list = []
        self.website = "https://acme.test"
        # id -> (summary, text)
        self.shared: dict[str, tuple[DocumentSummary, str]] = {}

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

    async def opportunities(self, limit=50):
        return []

    async def accounts(self, limit=50):
        return self.targets[:limit]

    async def drafts(self, limit=50):
        return self.drafted[:limit]

    async def documents(self, limit=50):
        return [summary for summary, _ in reversed(self.shared.values())][:limit]

    async def document_text(self, document_id):
        return self.shared.get(document_id)

    async def suggestions(self, limit=50):
        return self.suggested

    async def icp(self):
        return self.saved_icp

    async def save_icp(self, icp) -> None:
        self.saved_icp = icp

    async def competitors(self, limit=50) -> list[CompetitorSummary]:
        return self.tracked[:limit]

    # Changes: saved and removed items by id, as (kind, name).
    async def set_saved(self, kind, ids, verdict) -> ItemsChanged:
        self.saved_changes = getattr(self, "saved_changes", []) + [(kind, list(ids), verdict)]
        return ItemsChanged(changed=[NamedItem(id=i, name=f"{kind} {i}") for i in ids if not i.startswith("x")],
                            missing=[i for i in ids if i.startswith("x")])

    async def removed(self, kind, limit=50):
        return []

    async def retract_facts(self, ids) -> ItemsChanged:
        self.superseded.update(ids)
        return ItemsChanged(changed=[NamedItem(id=i, name=i) for i in ids])

    async def contacts(self, limit=100):
        return getattr(self, "people", [])[:limit]

    async def add_contact(self, contact) -> ContactSummary:
        added = ContactSummary(id=f"p{next(self._ids)}", name=contact.name, email=contact.email,
                               company=contact.company, account_id="a-new", approved=True)
        self.people = [*getattr(self, "people", []), added]
        return added

    async def remove_contacts(self, ids) -> ItemsChanged:
        return ItemsChanged(changed=[NamedItem(id=i, name=i) for i in ids])

    async def edit_draft(self, draft_id, subject, body) -> DraftSummary:
        for i, draft in enumerate(self.drafted):
            if draft.id == draft_id:
                self.drafted[i] = draft.model_copy(update={k: v for k, v in (("subject", subject), ("body", body)) if v})
                return self.drafted[i]
        raise KeyError(draft_id)

    async def discard_drafts(self, ids) -> ItemsChanged:
        gone = [d for d in self.drafted if d.id in ids]
        self.drafted = [d for d in self.drafted if d.id not in ids]
        return ItemsChanged(changed=[NamedItem(id=d.id, name=d.recipient) for d in gone],
                            missing=[i for i in ids if i not in {d.id for d in gone}])

    async def propose_action(self, action) -> str:
        self.proposed.append(action)
        return f"a{len(self.proposed)}"


class RecordingJobs:
    def __init__(self, refuse: str | None = None):
        self.started: list[tuple[str, dict]] = []
        self.refuse = refuse
        self.busy: list = []

    async def start(self, kind, params):
        if self.refuse:
            raise JobRefused(self.refuse)
        self.started.append((kind, params))
        return f"job-{len(self.started)}"

    async def running(self):
        return list(self.busy)


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
