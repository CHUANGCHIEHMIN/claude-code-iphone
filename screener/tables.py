"""Generic helpers for the table-shaped JSON that TWSE / TPEx return."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


@dataclass
class Table:
    title: str
    fields: list[str]
    data: list[list]
    groups: list = field(default_factory=list)


def norm(s) -> str:
    return _WS.sub("", _TAG.sub("", str(s or "")))


def num(v) -> float | None:
    """Parse '1,234.5', '-', '--', '<p>+</p>', 'X0.00', '' -> float | None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = norm(v).replace(",", "").replace("％", "").replace("%", "")
    s = s.lstrip("Xx+")
    if s in ("", "-", "--", "---", "N/A", "除權息", "除權", "除息"):
        return None
    try:
        return float(s)
    except ValueError:
        m = re.match(r"^-?\d+(\.\d+)?", s)
        return float(m.group(0)) if m else None


def extract_tables(js) -> list[Table]:
    """Return every table found in a TWSE/TPEx JSON payload (new and legacy layouts)."""
    out: list[Table] = []
    if not isinstance(js, dict):
        return out
    for t in js.get("tables") or []:
        if isinstance(t, dict) and t.get("data"):
            out.append(Table(norm(t.get("title")), [norm(f) for f in t.get("fields") or []],
                             t["data"], t.get("groups") or []))
    if js.get("data") and js.get("fields"):
        out.append(Table(norm(js.get("title")), [norm(f) for f in js["fields"]], js["data"]))
    # TWSE legacy MI_INDEX style: fields9/data9 ...
    for k, v in js.items():
        m = re.fullmatch(r"fields(\d+)", k)
        if m and js.get(f"data{m.group(1)}"):
            out.append(Table(k, [norm(f) for f in v], js[f"data{m.group(1)}"]))
    if js.get("aaData"):
        out.append(Table("aaData", [], js["aaData"]))
    return out


def find_table(tables: list[Table], *must: str) -> Table | None:
    for t in tables:
        joined = "|".join(t.fields)
        if all(m in joined for m in must):
            return t
    return None


def col(fields: list[str], *must: str, exclude: tuple[str, ...] = (), start: int = 0) -> int | None:
    for i, f in enumerate(fields):
        if i < start:
            continue
        if all(m in f for m in must) and not any(x in f for x in exclude):
            return i
    return None


def is_ok(js) -> bool:
    if not isinstance(js, dict):
        return bool(js)
    stat = str(js.get("stat", "OK")).upper()
    return stat in ("OK", "") and bool(extract_tables(js))
