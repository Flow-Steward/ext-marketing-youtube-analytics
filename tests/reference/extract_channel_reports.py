#!/usr/bin/env python3
"""Extract the report tables of YouTube's channel reports page from its pinned copy.

Source: https://developers.google.com/youtube/analytics/channel_reports?hl=en
("YouTube Analytics API: Channel Reports"), downloaded 2026-11-23 into
tests/reference/sources/channel_reports.html. The page itself is not committed (it
carries the site's own scripts); its SHA-256 is pinned here and the extracted tables
are committed as channel_reports.json. Run from the bundle root:

    python3 -I tests/reference/extract_channel_reports.py

Each table of the page (``table.yt-analytics-report-details``) is one report: the
dimensions, metrics and filters it allows, grouped as the page groups them with its
usage terms ("Required", "Optional", "Use exactly 1", "Use 1 or more", "Use 0 or 1",
"Use 0 or more"), the sorting options when the table lists them, and the notes that
apply to it. A metric marked with an asterisk is a monetary metric ("metrics marked
with an asterisk (*) are monetary metrics that require this scope and monetization
status"). From the notes two rules are taken as data: "requires you to set the
maxResults parameter to an integer value of N or less" and "also requires you to
specify a value for the sort request parameter". A page with another SHA-256 is
refused: the pinned facts change only on purpose.
"""

from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "sources" / "channel_reports.html"
OUTPUT = HERE / "channel_reports.json"
URL = "https://developers.google.com/youtube/analytics/channel_reports?hl=en"
SHA256 = "6824db16b213e37c96c15abfbbb96f809a41c914cd30b40645fd559b807be338"
BYTES = 306166
DOWNLOADED = "2026-11-23"

#: The page's usage terms -> (fewest, most) values of the group; None is "all of them".
USAGE: dict[str, tuple[int, int | None]] = {
    "Required": (-1, None),
    "Optional": (0, None),
    "Use exactly 1": (1, 1),
    "Use 1 or more": (1, None),
    "Use 0 or 1": (0, 1),
    "Use 0 or more": (0, None),
}
_HEADINGS = ("h2", "h3", "h4", "h5")
_VOID = {"br", "img", "hr", "input", "meta", "link", "wbr", "source", "col"}
_VALUE = re.compile(r"-?[A-Za-z][A-Za-z0-9]*(?:==[A-Za-z0-9_]+)?\*?")
_MAX_RESULTS = re.compile(r"maxResults\s+parameter to an?\s+integer value of\s+(\d+)\s+or less")
_SORT_REQUIRED = re.compile(r"requires? you to specify a value for the\s+sort\s+request parameter")
_UPDATED = re.compile(r"Last updated (\d{4}-\d{2}-\d{2}) UTC")


class _Node:
    def __init__(self, tag: str, attrs: dict[str, str], parent: _Node | None) -> None:
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children: list[_Node | str] = []

    def text(self, *, breaks: bool = False) -> str:
        parts: list[str] = []
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            elif child.tag == "br" and breaks:
                parts.append(", ")
            elif child.tag not in {"script", "style"}:
                parts.append(child.text(breaks=breaks))
        return "".join(parts)

    def elements(self, tag: str | None = None) -> list[_Node]:
        return [c for c in self.children if isinstance(c, _Node) and (tag is None or c.tag == tag)]

    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())


class _Tree(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", {}, None)
        self.node = self.root

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag, {k: v or "" for k, v in attrs}, self.node)
        self.node.children.append(node)
        if tag not in _VOID:
            self.node = node

    def handle_endtag(self, tag: str) -> None:
        node: _Node | None = self.node
        while node is not None and node.tag != tag:
            node = node.parent
        if node is not None and node.parent is not None:
            self.node = node.parent

    def handle_data(self, data: str) -> None:
        self.node.children.append(data)


def _squash(text: str) -> str:
    return " ".join(text.split())


def _values(cell: _Node) -> list[str]:
    """The names a value cell lists, before any note in it."""
    text = cell.text(breaks=True).split("Note:")[0]
    # Remarks in parentheses, such as "(see note below table)", are not values.
    text = re.sub(r"\([^)]*\)", " ", text)
    return [v for v in _VALUE.findall(text) if v.rstrip("*") != "None"]


def _cell_note(cell: _Node) -> str | None:
    text = _squash(cell.text())
    return "Note:" + text.split("Note:", 1)[1] if "Note:" in text else None


def _group(usage: str, values: list[str]) -> dict[str, Any]:
    if usage not in USAGE:
        raise SystemExit(f"unknown usage term in a report table: {usage!r}")
    low, high = USAGE[usage]
    count = len(values)
    return {
        "usage": usage,
        "values": values,
        "min": count if low < 0 else low,
        "max": count if high is None else high,
    }


def _report(table: _Node, title: str, section: list[str], notes: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "title": title,
        "section": section,
        "dimensions": [],
        "metrics": [],
        "monetary_metrics": [],
        "filters": [],
        "fixed_filters": {},
        "sort_options": None,
    }
    body = [n for n in table.elements() if n.tag in {"tbody", "thead"}]
    rows = [r for part in body for r in part.elements("tr")]
    own_notes: list[str] = []
    for row in rows:
        cells = row.elements("td")
        if len(cells) != 2:
            continue
        label = _squash(cells[0].text()).rstrip(":").lower()
        if label == "sorting options":
            out["sort_options"] = _values(cells[1])
            continue
        if label not in {"dimensions", "metrics", "filters"}:
            raise SystemExit(f"{title}: unknown row {label!r}")
        inner = [t for t in cells[1].elements("table")]
        groups: list[dict[str, Any]] = []
        for sub in inner:
            sub_rows = [r for part in sub.elements("tbody") for r in part.elements("tr")]
            sub_rows += sub.elements("tr")
            for sub_row in sub_rows:
                pair = sub_row.elements("td")
                if len(pair) != 2:
                    continue
                usage = _squash(pair[0].text())
                if usage == "[None]":
                    continue
                values = _values(pair[1])
                note = _cell_note(pair[1])
                if note:
                    own_notes.append(note)
                if not values:
                    raise SystemExit(f"{title}: {label} group {usage!r} lists no values")
                if label == "metrics":
                    out["monetary_metrics"] += [v.rstrip("*") for v in values if v.endswith("*")]
                    values = [v.rstrip("*") for v in values]
                if label == "filters":
                    names = []
                    # "insightTrafficSourceType==ADVERTISING (or another supported value)"
                    # is an example value, not the only one.
                    example = "another supported value" in _squash(pair[1].text())
                    for value in values:
                        name, _, fixed = value.partition("==")
                        if fixed and not example:
                            out["fixed_filters"][name] = fixed
                        names.append(name)
                    values = names
                groups.append(_group(usage, values))
        out[label] = groups
    if not out["metrics"]:
        raise SystemExit(f"{title}: the table lists no metrics")
    all_notes = notes + own_notes
    out["notes"] = all_notes
    limit = None
    sort_required = False
    for note in all_notes:
        match = _MAX_RESULTS.search(note)
        if match:
            limit = int(match.group(1))
        if _SORT_REQUIRED.search(note):
            sort_required = True
    out["max_results"] = limit
    out["sort_required"] = sort_required
    # "Ad performance reports require an authorization token that grants access to the
    # https://www.googleapis.com/auth/yt-analytics-monetary.readonly scope."
    out["monetary_scope_required"] = any(
        "yt-analytics-monetary.readonly" in note and "require" in note for note in notes
    )
    return out


def extract(raw: bytes) -> dict[str, Any]:
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SHA256:
        raise SystemExit(f"the documentation page changed (SHA-256 {digest}); pin it again")
    page = raw.decode("utf-8")
    tree = _Tree()
    tree.feed(page)
    article = _find_article(tree.root)
    reports: list[dict[str, Any]] = []
    # (level, title, notes) of the headings that are open at this point.
    stack: list[tuple[int, str, list[str]]] = []

    def walk(node: _Node) -> None:
        for child in node.children:
            if not isinstance(child, _Node):
                continue
            if child.tag in _HEADINGS:
                level = int(child.tag[1])
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, _squash(child.text()), []))
            elif child.tag == "p" and child.classes() & {"note", "caution", "warning", "special"}:
                if stack:
                    stack[-1][2].append(_squash(child.text()))
            elif child.tag == "table" and "yt-analytics-report-details" in child.classes():
                if _squash(child.text()).split()[:2] != ["Property", "Value"]:
                    # A list of metrics, not a report (its columns are not Property, Value).
                    continue
                if not stack:
                    raise SystemExit("a report table comes before any heading")
                notes = [n for _, _, ns in stack for n in ns]
                reports.append(_report(child, stack[-1][1], [h for _, h, _ in stack[:-1]], notes))
            else:
                walk(child)

    walk(article)
    # The page's own example table ("Understanding report tables") is not a report.
    reports = [r for r in reports if r["title"] != "Understanding report tables"]
    seen: dict[str, int] = {}
    for report in reports:
        title = report["title"]
        seen[title] = seen.get(title, 0) + 1
        report["id"] = f"{title} ({seen[title]})" if seen[title] > 1 else title
    for report in reports:
        if seen[report["title"]] > 1 and not report["id"].endswith(")"):
            report["id"] = f"{report['title']} (1)"
    updated = _UPDATED.search(page)
    return {
        "source": {
            "url": URL,
            "sha256": SHA256,
            "bytes": BYTES,
            "downloaded": DOWNLOADED,
            "last_updated": updated.group(1) if updated else None,
        },
        "reports": reports,
    }


def _find_article(root: _Node) -> _Node:
    found: list[_Node] = []

    def walk(node: _Node) -> None:
        for child in node.elements():
            if child.tag == "div" and "devsite-article-body" in child.classes():
                found.append(child)
                return
            walk(child)

    walk(root)
    if len(found) != 1:
        raise SystemExit("the page has no single article body")
    return found[0]


def main() -> int:
    facts = extract(SOURCE.read_bytes())
    OUTPUT.write_text(json.dumps(facts, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print("channel reports:", len(facts["reports"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
