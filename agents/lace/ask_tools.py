"""The Lace's questions to the founder, answered with a click instead of a
message: a choice, a checklist to tick, or a short form. Each puts a block
under the reply; the founder's answer comes back as their next message."""

from langchain_core.tools import BaseTool, tool

from agents.lace.tool_guard import guarded
from agents.schemas.lace import ToolResult
from agents.schemas.lace_ui import (ChecklistBlock, ChecklistItem, ChoicesBlock, FormBlock, FormField, SuggestionsBlock,
                                    new_block_id)

MIN_CHOICES, MAX_CHOICES = 2, 5
MIN_SUGGESTIONS, MAX_SUGGESTIONS = 2, 3
CHOICE_CHARS = 60
MAX_CHECKLIST_ITEMS = 20
MAX_FORM_FIELDS = 6
LABEL_CHARS = 120
SUBMIT_CHARS = 30


def _shown(block, what: str) -> ToolResult:
    return ToolResult.success(f"The founder will see {what} under your reply.", {"ui": [block.model_dump()]})


def _submit(label: str, fallback: str) -> str | None:
    """The button's label, or None when it is too long."""
    label = label.strip() or fallback
    return label if len(label) <= SUBMIT_CHARS else None


def build_ask_tools() -> list[BaseTool]:

    @tool(parse_docstring=True)
    @guarded
    async def ask_choice(question: str, options: list[str]) -> ToolResult:
        """Put a question to the founder with a few answers they can click instead of typing, shown under your reply. Use it when the next step turns on one choice between a few clear options (which country first, whether to go ahead). Keep your reply short and stop: say what you found, but don't list the options or ask the question again in your text. Their click comes back as their next message.

        Args:
            question: The question, in one short sentence.
            options: 2 to 5 short answers, each a few words, written as the founder would say them.
        """
        options = [o.strip() for o in options if o.strip()]
        if not question.strip():
            return ToolResult.failure("The question is empty.")
        if not MIN_CHOICES <= len(options) <= MAX_CHOICES:
            return ToolResult.failure(f"Give {MIN_CHOICES} to {MAX_CHOICES} options; got {len(options)}.")
        if any(len(o) > CHOICE_CHARS for o in options):
            return ToolResult.failure(f"Keep each option under {CHOICE_CHARS} characters.")
        return _shown(ChoicesBlock(id=new_block_id(), question=question.strip(), options=options), "these options")

    @tool(parse_docstring=True)
    @guarded
    async def ask_checklist(question: str, items: list[ChecklistItem], submit: str = "Go ahead") -> ToolResult:
        """Show the founder a checklist to tick, under your reply: which of several things to act on. Use it to pick several at once (which accounts to draft to, which competitors to track), and always to confirm before you change or remove two or more saved items: list exactly those, ticked, so they can untick any to keep. Their answer says which ids they left ticked and which they unticked. Keep your reply short and stop: their answer comes back as their next message.

        Args:
            question: What ticking means, in one short sentence (e.g. "Remove these opportunities?").
            items: 1 to 20 items. Give each the id of what it stands for (a saved item's id, or a short key), a few-word label, an optional one-line detail, and whether it starts ticked.
            submit: The button's label, a few words (e.g. "Remove ticked").
        """
        label = _submit(submit, "Go ahead")
        if not question.strip():
            return ToolResult.failure("The question is empty.")
        if not 1 <= len(items) <= MAX_CHECKLIST_ITEMS:
            return ToolResult.failure(f"Give 1 to {MAX_CHECKLIST_ITEMS} items; got {len(items)}.")
        if len({i.id for i in items}) != len(items):
            return ToolResult.failure("Each item needs its own id.")
        if any(not i.label.strip() or len(i.label) > LABEL_CHARS for i in items):
            return ToolResult.failure(f"Give every item a label under {LABEL_CHARS} characters.")
        if label is None:
            return ToolResult.failure(f"Keep the button label under {SUBMIT_CHARS} characters.")
        block = ChecklistBlock(id=new_block_id(), question=question.strip(), items=items, submit=label)
        return _shown(block, "this checklist")

    @tool(parse_docstring=True)
    @guarded
    async def ask_form(question: str, fields: list[FormField], submit: str = "Send") -> ToolResult:
        """Ask the founder for a few specific details as a short form under your reply, instead of making them type it out: a person's name and email to add, a link, a number. Fill in any field you can already guess so they only correct it. Keep your reply short and stop: their answer comes back as their next message.

        Args:
            question: What the details are for, in one short sentence.
            fields: 1 to 6 fields, each with a name (the key the answer comes back under), a label, a kind (text, long_text, email, url or number), whether it is required, and an optional value to start with.
            submit: The button's label, a few words.
        """
        label = _submit(submit, "Send")
        if not question.strip():
            return ToolResult.failure("The question is empty.")
        if not 1 <= len(fields) <= MAX_FORM_FIELDS:
            return ToolResult.failure(f"Give 1 to {MAX_FORM_FIELDS} fields; got {len(fields)}.")
        if len({f.name for f in fields}) != len(fields) or any(not f.name.strip() for f in fields):
            return ToolResult.failure("Each field needs its own name.")
        if any(not f.label.strip() or len(f.label) > LABEL_CHARS for f in fields):
            return ToolResult.failure(f"Give every field a label under {LABEL_CHARS} characters.")
        if label is None:
            return ToolResult.failure(f"Keep the button label under {SUBMIT_CHARS} characters.")
        return _shown(FormBlock(id=new_block_id(), question=question.strip(), fields=fields, submit=label), "this form")

    @tool(parse_docstring=True)
    @guarded
    async def suggest_replies(options: list[str]) -> ToolResult:
        """Offer the founder likely replies to the question your answer ends on, as chips they can tap to send (e.g. after "Want me to dig deeper into one of them?": "Check Hamtech's LinkedIn", "Look for their OTA guide"). They can still type anything, so this is not for a decision you need answered (that is ask_choice). Call it last, after writing your answer.

        Args:
            options: 2 or 3 short replies, each a few words, written as the founder would say them.
        """
        options = [o.strip() for o in options if o.strip()]
        if not MIN_SUGGESTIONS <= len(options) <= MAX_SUGGESTIONS:
            return ToolResult.failure(f"Give {MIN_SUGGESTIONS} or {MAX_SUGGESTIONS} options; got {len(options)}.")
        if any(len(o) > CHOICE_CHARS for o in options):
            return ToolResult.failure(f"Keep each option under {CHOICE_CHARS} characters.")
        return _shown(SuggestionsBlock(options=options), "these suggested replies")

    return [ask_choice, ask_checklist, ask_form, suggest_replies]
