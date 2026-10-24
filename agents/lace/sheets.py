"""Reading a sheet's rows into what a Lace can say about them, in code, so the
model never adds up a column itself: per column how many cells are filled,
the totals of a numeric column, and the counts of a column with few values
(a pipeline stage, a status)."""

import re

# A column is numeric when this share of its filled cells reads as a number.
NUMERIC_SHARE = 0.8
# A text column is counted by value when it has at most this many values.
MAX_GROUPS = 12
_NUMBER = re.compile(r"^[^\d\-]*(-?[\d,]*\.?\d+)\s*%?[^\d]*$")
_SHEET_ID = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]{20,})")


def sheet_id(url: str) -> str | None:
    """The spreadsheet's id from its link (docs.google.com/spreadsheets/d/<id>/...)."""
    match = _SHEET_ID.search(url or "")
    return match.group(1) if match else None


def number(cell: str) -> float | None:
    """A cell as a number: "KES 1,200", "$3.5", "40%" and "-7" all read."""
    match = _NUMBER.match(cell.strip()) if cell else None
    return float(match.group(1).replace(",", "")) if match else None


def summarise(rows: list[list[str]]) -> dict:
    """{rows, columns: [{name, filled, sum/min/max/average | counts}]} for a
    tab whose first row is its header."""
    if not rows:
        return {"rows": 0, "columns": []}
    header, body = rows[0], rows[1:]
    columns = []
    for i, name in enumerate(header):
        cells = [r[i].strip() for r in body if i < len(r) and str(r[i]).strip()]
        column: dict = {"name": name or f"Column {i + 1}", "filled": len(cells)}
        numbers = [n for n in (number(c) for c in cells) if n is not None]
        if cells and len(numbers) >= NUMERIC_SHARE * len(cells):
            column.update(sum=round(sum(numbers), 2), min=min(numbers), max=max(numbers),
                          average=round(sum(numbers) / len(numbers), 2))
        elif cells and len(set(cells)) <= MAX_GROUPS and len(set(cells)) < len(cells):
            counts: dict[str, int] = {}
            for cell in cells:
                counts[cell] = counts.get(cell, 0) + 1
            column["counts"] = dict(sorted(counts.items(), key=lambda kv: -kv[1]))
        columns.append(column)
    return {"rows": len(body), "columns": columns}
