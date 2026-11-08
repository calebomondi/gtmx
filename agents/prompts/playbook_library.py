"""GTM playbooks: how a good go-to-market operator does each kind of task
(a cold email, a follow-up, a reply, judging a lead), kept as short Markdown
files in agents/prompts/playbooks/, read by both the Lace and the outreach
pipelines.

The agent-skills pattern: the Lace's prompt lists only each playbook's name and
when to use it, and it reads the whole playbook (read_playbook) when it starts
that kind of task. Pipelines that always need one load it directly. The
founder's standing instructions outrank a playbook.

Each file starts with a small front matter block:

    ---
    name: cold-email
    use_when: Writing a first email to someone who never heard from the founder.
    sources:
    - Where the method came from, credited
    ---
"""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

PLAYBOOK_DIR = Path(__file__).resolve().parent / "playbooks"


class PlaybookError(ValueError):
    """A playbook file without a usable front matter: a packaging mistake,
    caught by the tests rather than met by a founder."""


@dataclass(frozen=True)
class Playbook:
    name: str
    use_when: str
    sources: tuple[str, ...]
    body: str


def parse(text: str) -> Playbook:
    """One playbook file's front matter and body."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---" or "---" not in (line.strip() for line in lines[1:]):
        raise PlaybookError("A playbook starts with a front matter block between --- lines.")
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    fields: dict[str, str] = {}
    sources: list[str] = []
    for line in lines[1:end]:
        if line.startswith("- "):
            sources.append(line[2:].strip())
        elif ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    if not fields.get("name") or not fields.get("use_when"):
        raise PlaybookError("A playbook's front matter needs a name and a use_when line.")
    return Playbook(name=fields["name"], use_when=fields["use_when"], sources=tuple(sources),
                    body="\n".join(lines[end + 1:]).strip())


@cache
def playbooks() -> dict[str, Playbook]:
    """Every playbook by name, read once per process."""
    found = [parse(path.read_text(encoding="utf-8")) for path in sorted(PLAYBOOK_DIR.glob("*.md"))]
    return {p.name: p for p in found}


def playbook(name: str) -> Playbook | None:
    return playbooks().get(name.strip().lower())


def render_index() -> str:
    """The prompt's list: one line per playbook, its name and when to use it."""
    return "\n".join(f"- {p.name}: {p.use_when}" for p in playbooks().values())


def playbook_section(name: str) -> str:
    """A playbook as a section of a pipeline's prompt, under the pipeline's own
    rules: where the two differ, the rules above it win (they are what the
    draft is checked against)."""
    found = playbook(name)
    if found is None:
        raise PlaybookError(f"No playbook called {name!r}.")
    return (f"\nTHE {found.name.upper()} PLAYBOOK (the method behind the rules above; where they differ, "
            f"the rules above win)\n{found.body}\n")
