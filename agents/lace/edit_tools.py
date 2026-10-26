"""The Lace's tools for changing what it has saved, when the founder asks:
saving or removing finds, correcting what it knows, adding or removing
people, and rewriting or discarding drafts. Sending is never one of them: a
message goes out only on the founder's click.

Changing two or more items waits for the founder to confirm them on a
checklist (see the prompt); one item is changed straight away."""

from langchain_core.tools import BaseTool, tool
from pydantic import ValidationError

from agents.lace.store import LaceStore
from agents.lace.tool_guard import guarded
from agents.schemas.lace import ItemsChanged, NewContact, SavedKind, SavedVerdict, ToolResult

MAX_IDS = 20
REMOVED_PER_READ = 50
CONTACTS_PER_READ = 100
_PLURAL = {"competitor": "competitors", "account": "accounts", "opportunity": "opportunities"}


def _ids(ids: list[str]) -> list[str] | None:
    """The distinct ids, in order; None when there are none or too many."""
    unique = list(dict.fromkeys(i.strip() for i in ids if i.strip()))
    return unique if 0 < len(unique) <= MAX_IDS else None


def _report(done: str, result: ItemsChanged) -> ToolResult:
    names = ", ".join(item.name for item in result.changed)
    missing = f" No match for: {', '.join(result.missing)}." if result.missing else ""
    if not result.changed:
        return ToolResult.failure(f"Nothing changed.{missing}")
    return ToolResult.success(f"{done}: {names}.{missing}", result.model_dump())


_TOO_MANY = ToolResult.failure(f"Give 1 to {MAX_IDS} ids.")


def build_edit_tools(store: LaceStore) -> list[BaseTool]:

    @tool(parse_docstring=True)
    @guarded
    async def update_saved(kind: SavedKind, ids: list[str], verdict: SavedVerdict) -> ToolResult:
        """Save or remove competitors, accounts or opportunities, when the founder asks (e.g. "remove the opportunities that don't fit what we sell"). Remove takes them out of every list and stops them being suggested again; save puts them back or keeps a suggestion. For two or more, confirm with ask_checklist first and change only what they left ticked.

        Args:
            kind: competitor, account or opportunity.
            ids: The ids, from list_competitors, list_accounts, list_opportunities, list_suggestions or list_removed.
            verdict: save or remove.
        """
        chosen = _ids(ids)
        if chosen is None:
            return _TOO_MANY
        done = "Saved" if verdict == "save" else "Removed"
        return _report(done, await store.set_saved(kind, chosen, verdict))

    @tool(parse_docstring=True)
    @guarded
    async def list_removed(kind: SavedKind) -> ToolResult:
        """The competitors, accounts or opportunities the founder removed, newest first, to save one back when they ask.

        Args:
            kind: competitor, account or opportunity.
        """
        rows = await store.removed(kind, REMOVED_PER_READ)
        return ToolResult.success(f"{len(rows)} removed {_PLURAL[kind]}.", [r.model_dump() for r in rows])

    @tool(parse_docstring=True)
    @guarded
    async def forget_facts(ids: list[str]) -> ToolResult:
        """Drop facts that are wrong or out of date, when the founder says so. To fix a fact instead, record the right one with record_fact and replaces_id. For two or more, confirm with ask_checklist first.

        Args:
            ids: The fact ids, from get_facts.
        """
        chosen = _ids(ids)
        if chosen is None:
            return _TOO_MANY
        return _report("Forgot", await store.retract_facts(chosen))

    @tool(parse_docstring=True)
    @guarded
    async def list_contacts() -> ToolResult:
        """The people at the saved accounts: who they are, where, how to reach them, and whether the founder approved them for outreach."""
        rows = await store.contacts(CONTACTS_PER_READ)
        return ToolResult.success(f"{len(rows)} contacts.", [r.model_dump(exclude_none=True) for r in rows])

    @tool(parse_docstring=True)
    @guarded
    async def add_contact(company: str, name: str, email: str | None = None, title: str | None = None,
                          linkedin: str | None = None, x: str | None = None, instagram: str | None = None,
                          facebook: str | None = None, tiktok: str | None = None,
                          website: str | None = None) -> ToolResult:
        """Add a person the founder names, approved for outreach, at a company. The company becomes a saved account if it is not one yet. If you lack their name or company, ask with ask_form first.

        Args:
            company: The company they work at.
            name: Their full name.
            email: Their email address, if known.
            title: Their role, if known.
            linkedin: Their LinkedIn profile URL, if known.
            x: Their own X profile URL or handle, if known.
            instagram: Their own Instagram profile URL or handle, if known.
            facebook: Their own Facebook profile URL, if known.
            tiktok: Their own TikTok profile URL or handle, if known.
            website: The company's website, if known.
        """
        try:
            person = NewContact(company=company.strip(), name=name.strip(), email=email and email.strip() or None,
                                title=title, linkedin=linkedin, x=x, instagram=instagram, facebook=facebook,
                                tiktok=tiktok, website=website)
        except ValidationError:
            return ToolResult.failure("Give at least a company and a name, each within normal length.")
        if not (person.email or person.linkedin or person.x or person.instagram or person.facebook or person.tiktok):
            note = " They have no email or social account yet, so nothing can be drafted to them until you add one."
        else:
            note = ""
        saved = await store.add_contact(person)
        return ToolResult.success(f"Added {saved.name} at {saved.company}, approved for outreach.{note}",
                                  saved.model_dump(exclude_none=True))

    @tool(parse_docstring=True)
    @guarded
    async def remove_contacts(ids: list[str]) -> ToolResult:
        """Remove people from the contacts, when the founder asks. For two or more, confirm with ask_checklist first.

        Args:
            ids: The contact ids, from list_contacts.
        """
        chosen = _ids(ids)
        if chosen is None:
            return _TOO_MANY
        return _report("Removed", await store.remove_contacts(chosen))

    @tool(parse_docstring=True)
    @guarded
    async def edit_draft(draft_id: str, subject: str | None = None, body: str | None = None) -> ToolResult:
        """Rewrite an unsent draft the way the founder asks (shorter, warmer, a different angle). It still waits for them to send it.

        Args:
            draft_id: The draft's id, from an update or show.
            subject: The new subject line (email only); omit to keep it.
            body: The new message; omit to keep it.
        """
        if subject is None and body is None:
            return ToolResult.failure("Give a new subject or body.")
        if body is not None and not body.strip():
            return ToolResult.failure("The new body is empty.")
        try:
            draft = await store.edit_draft(draft_id, subject, body)
        except KeyError:
            return ToolResult.failure(f"No unsent draft has id {draft_id}.")
        except ValueError as exc:
            return ToolResult.failure(str(exc))
        return ToolResult.success(f"Rewrote the draft to {draft.recipient} at {draft.company}.", draft.model_dump())

    @tool(parse_docstring=True)
    @guarded
    async def discard_drafts(ids: list[str]) -> ToolResult:
        """Throw away unsent drafts, when the founder asks. Sent messages are never touched. For two or more, confirm with ask_checklist first.

        Args:
            ids: The draft ids.
        """
        chosen = _ids(ids)
        if chosen is None:
            return _TOO_MANY
        return _report("Discarded drafts to", await store.discard_drafts(chosen))

    return [update_saved, list_removed, forget_facts, list_contacts, add_contact, remove_contacts, edit_draft,
            discard_drafts]
