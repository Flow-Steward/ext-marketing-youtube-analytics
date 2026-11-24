"""One label for each input name, and one description for inputs that mean the same in
every step.

A step's form shows the label and the description. An input with the same name has the
same label in every step (``LABELS``, otherwise the name in words); an input that means
the same in every step also has the same description (``SAME``). An input whose meaning
depends on the method (``part``, ``id``, ``mine``) keeps the description the source gives
for that method; where the source gives none, ``FALLBACK`` says it.
"""

from __future__ import annotations

_WORDS = {"id": "ID", "ids": "IDs", "url": "URL", "html": "HTML"}

LABELS: dict[str, str] = {
    "id": "IDs",
    "ids": "Report owner",
    "mine": "Mine",
    "start_date": "Start date",
    "end_date": "End date",
    "metrics": "Metrics",
    "dimensions": "Dimensions",
    "filters": "Filters",
    "sort": "Sort",
    "max_results": "Most rows",
    "start_index": "First row",
    "currency": "Currency",
    "include_historical_channel_data": "Include historical channel data",
    "page_token": "Page token",
    "max_items": "Most records",
    "max_groups": "Most groups",
    "all_pages": "All pages",
    "skip": "Skip",
    "body": "Request body",
    "group_id": "Group ID",
    "item_type": "Item type",
    "output": "Output",
    "on_behalf_of_content_owner": "On behalf of content owner",
}

SAME: dict[str, str] = {
    "page_token": (
        "The page to start from: next_page_token of an earlier run that stopped early, or a "
        "nextPageToken YouTube returned."
    ),
    "skip": (
        "With page_token: how many records of that page an earlier run already returned "
        "(its next_skip)."
    ),
    "start_date": "The first day of the report, YYYY-MM-DD.",
    "end_date": "The last day of the report, YYYY-MM-DD.",
    "currency": (
        "The currency of revenue metrics, an ISO 4217 code such as EUR (YouTube's default: USD)."
    ),
    "on_behalf_of_content_owner": (
        "For YouTube content partners only: the content owner the request is made for. The "
        "connection must be authorized by a CMS account linked to that content owner."
    ),
}

FALLBACK: dict[str, str] = {}


def label_of(name: str) -> str:
    """The label of an input: LABELS, or its name in words."""
    if name in LABELS:
        return LABELS[name]
    words = [_WORDS.get(w, w) for w in name.split("_")]
    text = " ".join(words)
    return text[:1].upper() + text[1:]


def text_of(name: str, description: str | None) -> tuple[str, str]:
    """(label, description) of one input."""
    label = label_of(name)
    if name in SAME:
        return label, SAME[name]
    given = (description or "").strip()
    raw = name.replace("_", "")
    if not given or given.lower().replace(" ", "") in {raw, name.lower()}:
        given = FALLBACK.get(name, "")
    if not given:
        raise ValueError(f"No description for input {name}")
    return label, given
