"""Titles, one-line summaries and areas of the generated steps.

Keyed by the method id of the pinned Discovery document. The summary says in plain
words what the method does; build_contracts.py adds the facts of the source (scopes,
paging) to it.
"""

from __future__ import annotations

#: Method id -> (title, summary).
TITLES: dict[str, tuple[str, str]] = {
    # Reports
    "youtubeAnalytics.reports.query": (
        "Query analytics report",
        "Reads a YouTube Analytics report: metrics by dimensions for a channel or content "
        "owner over a date range.",
    ),
    # Groups
    "youtubeAnalytics.groups.list": (
        "Get analytics groups",
        "Reads YouTube Analytics groups by ID or of the connected account.",
    ),
    "youtubeAnalytics.groups.insert": (
        "Create analytics group",
        "Creates a YouTube Analytics group of videos, playlists, channels or assets.",
    ),
    "youtubeAnalytics.groups.update": (
        "Update analytics group",
        "Changes a YouTube Analytics group, for example its title.",
    ),
    "youtubeAnalytics.groups.delete": (
        "Delete analytics group",
        "Deletes a YouTube Analytics group.",
    ),
    "youtubeAnalytics.groupItems.list": (
        "Get analytics group items",
        "Reads the items of a YouTube Analytics group.",
    ),
    "youtubeAnalytics.groupItems.insert": (
        "Add analytics group item",
        "Adds an item to a YouTube Analytics group.",
    ),
    "youtubeAnalytics.groupItems.delete": (
        "Remove analytics group item",
        "Removes an item from a YouTube Analytics group.",
    ),
}

#: Method ids of the source that have no step, each with the reason (none: every method
#: of the YouTube Analytics API v2 has its own step).
EXCLUDED: dict[str, str] = {}

#: Area -> the resources (second part of the method id) it holds, in page order.
AREAS: dict[str, list[str]] = {
    "Reports": ["reports"],
    "Groups": ["groups", "groupItems"],
}

#: The verbs a step title may start with.
VERBS = {
    "Get",
    "Update",
    "Create",
    "Delete",
    "Upload",
    "Set",
    "Remove",
    "Rate",
    "Report",
    "Search",
    "Download",
    "Mark",
    "Bind",
    "Change",
    "Insert",
    "Send",
    "Ban",
    "Add",
    "Query",
    "Test",
    "List",
    "Reply",
    "Check",
}
