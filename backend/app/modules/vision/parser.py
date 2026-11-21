"""Deterministic shopping-list parser (quantities, units, vernacular terms)."""

from __future__ import annotations

import re
from dataclasses import dataclass

COUNT_UNITS = {
    "pc",
    "pcs",
    "piece",
    "pieces",
    "packet",
    "packets",
    "pack",
    "packs",
    "nos",
    "no",
    "unit",
    "units",
    "bottle",
    "bottles",
    "box",
    "boxes",
}
SIZE_UNITS = {
    "kg": "kg",
    "kgs": "kg",
    "g": "g",
    "gm": "g",
    "gms": "g",
    "gram": "g",
    "grams": "g",
    "l": "l",
    "ltr": "l",
    "litre": "l",
    "liter": "l",
    "ml": "ml",
}
MAX_ITEMS = 30

_SPLIT = re.compile(r"[\n,;•]+")
_NUM_UNIT = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\b")
_X_QTY = re.compile(r"(?:\bx\s*(\d+)\b|\b(\d+)\s*x\b)", re.IGNORECASE)
_LEAD_NUM = re.compile(r"^\s*(\d+)\s+(?=\D)")
_BULLET = re.compile(r"^\s*(?:\d+[.)]|[-*])\s+")


@dataclass
class ParsedItem:
    line: str
    name: str
    search_query: str
    quantity: int
    size: str | None


def parse_list(text: str) -> list[ParsedItem]:
    from app.modules.i18n.service import normalize_query

    items: list[ParsedItem] = []
    for raw in _SPLIT.split(text or ""):
        line = _BULLET.sub("", raw).strip()
        if len(line) < 2:
            continue
        quantity = 1
        size = None
        work = line
        m = _X_QTY.search(work)
        if m:
            quantity = int(m.group(1) or m.group(2))
            work = (work[: m.start()] + work[m.end() :]).strip()
        for num, unit in _NUM_UNIT.findall(work):
            u = unit.lower()
            if u in COUNT_UNITS:
                quantity = int(float(num))
                work = re.sub(
                    rf"(?<![\w.]){re.escape(num)}\s*{re.escape(unit)}\b",
                    " ",
                    work,
                    count=1,
                )
            elif u in SIZE_UNITS:
                size = f"{num.rstrip('0').rstrip('.') if '.' in num else num}{SIZE_UNITS[u]}"
                work = re.sub(
                    rf"(?<![\w.]){re.escape(num)}\s*{re.escape(unit)}\b",
                    " ",
                    work,
                    count=1,
                )
        lead = _LEAD_NUM.match(work)
        if lead and quantity == 1:
            quantity = int(lead.group(1))
            work = work[lead.end() :]
        name = " ".join(work.split()).strip(" -:")
        if not name:
            continue
        normalized, _, _ = normalize_query(name)
        items.append(
            ParsedItem(
                line=line,
                name=name,
                search_query=normalized,
                quantity=max(1, min(quantity, 10)),
                size=size,
            )
        )
        if len(items) >= MAX_ITEMS:
            break
    return items
