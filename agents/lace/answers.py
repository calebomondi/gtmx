"""The founder's answer to a question under a Lace reply, as two texts: what
the Lace reads (with the ids it needs to act) and the short line the founder
sees as their message."""

from agents.schemas.lace_ui import BlockAnswer, ChecklistBlock, ChoicesBlock, FormBlock

VALUE_CHARS = 2_000


class AnswerError(ValueError):
    """The answer does not fit its question; the message says how."""


def _choice(block: ChoicesBlock, answer: BlockAnswer) -> tuple[str, str]:
    if len(answer.chosen) != 1 or answer.chosen[0] not in block.options:
        raise AnswerError("Pick one of the options.")
    return answer.chosen[0], answer.chosen[0]


def _checklist(block: ChecklistBlock, answer: BlockAnswer) -> tuple[str, str]:
    known = {item.id for item in block.items}
    if not set(answer.chosen) <= known:
        raise AnswerError("That answer ticks items that are not on the list.")
    ticked = [i for i in block.items if i.id in answer.chosen]
    unticked = [i for i in block.items if i.id not in answer.chosen]
    listed = lambda items: "; ".join(f"{i.label} (id {i.id})" for i in items) or "none"  # noqa: E731
    model = (f'[Answer to your checklist "{block.question}"] Ticked: {listed(ticked)}. '
             f"Left unticked: {listed(unticked)}. Act on the ticked ones only.")
    founder = f"{block.submit}: {', '.join(i.label for i in ticked)}" if ticked else "None of these"
    return model, founder


def _form(block: FormBlock, answer: BlockAnswer) -> tuple[str, str]:
    names = {f.name for f in block.fields}
    if not set(answer.values) <= names:
        raise AnswerError("That answer fills in fields the form does not have.")
    values = {k: v.strip() for k, v in answer.values.items()}
    if any(len(v) > VALUE_CHARS for v in values.values()):
        raise AnswerError(f"Keep each answer under {VALUE_CHARS} characters.")
    missing = [f.label for f in block.fields if f.required and not values.get(f.name)]
    if missing:
        raise AnswerError(f"Fill in: {', '.join(missing)}.")
    filled = [(f, values[f.name]) for f in block.fields if values.get(f.name)]
    model = (f'[Answer to your form "{block.question}"] '
             + "; ".join(f"{f.name} ({f.label}): {v}" for f, v in filled))
    founder = " · ".join(f"{f.label}: {v}" for f, v in filled)
    return model, founder


def describe(block: ChoicesBlock | ChecklistBlock | FormBlock, answer: BlockAnswer) -> tuple[str, str]:
    """(what the Lace reads, what the founder sees). Raises AnswerError when
    the answer does not fit the question."""
    if isinstance(block, ChoicesBlock):
        return _choice(block, answer)
    if isinstance(block, ChecklistBlock):
        return _checklist(block, answer)
    return _form(block, answer)
