"""The everyday steps: their inputs, outputs and descriptions.

They are built on top of the generated steps (runtime/composites.py) and come first in
the step list. Contract files are generated from this module by build_contracts.py.
"""

from __future__ import annotations

from typing import Any

#: GroupContentDetails.itemType in the pinned Discovery document: "Valid values for this
#: property are: youtube#channel, youtube#playlist, youtube#video, youtubePartner#asset".
ITEM_TYPES = ["youtube#video", "youtube#playlist", "youtube#channel", "youtubePartner#asset"]
#: The metrics Get top videos asks for when none are given (all in the table "Top videos
#: with optional regional filters" of the channel reports page).
TOP_VIDEO_METRICS = [
    "views",
    "estimatedMinutesWatched",
    "averageViewDuration",
    "likes",
    "subscribersGained",
]
TOP_VIDEO_SORTS = [
    "-views",
    "-redViews",
    "-estimatedRevenue",
    "-estimatedRedPartnerRevenue",
    "-estimatedMinutesWatched",
    "-estimatedRedMinutesWatched",
    "-subscribersGained",
    "-subscribersLost",
]

WARNINGS = {
    "name": "warnings",
    "type": "array",
    "items": {"type": "string"},
    "description": "What the step could not do fully or what to check.",
}

#: The outputs every write returns about what YouTube's answer confirms.
PROCESSING_OUTPUTS: list[dict[str, Any]] = [
    {
        "name": "processing",
        "type": ["string", "null"],
        "enum": ["completed", "accepted", None],
        "description": (
            "completed: YouTube answered that the change is made. None in a test run and when "
            "nothing was sent."
        ),
    },
    {
        "name": "applied",
        "type": ["boolean", "null"],
        "description": (
            "True with processing completed. False in a test run and when nothing was sent."
        ),
    },
    {
        "name": "check",
        "type": ["object", "null"],
        "additionalProperties": True,
        "description": "With processing accepted: operation_id, the step that reads the outcome.",
    },
]

#: The outputs of a list step.
PAGE_OUTPUTS: list[dict[str, Any]] = [
    {
        "name": "items",
        "type": "array",
        "items": {"type": "object", "additionalProperties": True},
        "description": "The records read.",
    },
    {"name": "count", "type": "integer", "description": "How many records were read."},
    {
        "name": "complete",
        "type": "boolean",
        "description": "True when the list was read to its end.",
    },
    {
        "name": "next_page_token",
        "type": ["string", "null"],
        "description": "When complete is false: the page_token to start the next run from.",
    },
]

EFFECT_OUTPUTS: list[dict[str, Any]] = [
    {"name": "external_effect_status", "type": "string"},
    {"name": "definitely_no_external_effect", "type": "boolean"},
]


def _text(name: str, title: str, description: str, **extra: Any) -> dict[str, Any]:
    return {"name": name, "title": title, "description": description, "type": "string", **extra}


START = _text(
    "start_date",
    "From",
    "The first day, YYYY-MM-DD.",
    maxLength=10,
    pattern=r"^\d{4}-\d{2}-\d{2}$",
    required=True,
)
END = _text(
    "end_date",
    "To",
    "The last day, YYYY-MM-DD.",
    maxLength=10,
    pattern=r"^\d{4}-\d{2}-\d{2}$",
    required=True,
)
METRICS = {
    "name": "metrics",
    "title": "Metrics",
    "type": "array",
    "items": {"type": "string", "maxLength": 100},
    "minItems": 1,
    "maxItems": 50,
    "required": True,
    "description": (
        "YouTube Analytics metrics, such as views, estimatedMinutesWatched, likes, "
        "subscribersGained."
    ),
}
DIMENSIONS = {
    "name": "dimensions",
    "title": "Dimensions",
    "type": "array",
    "items": {"type": "string", "maxLength": 100},
    "maxItems": 10,
    "description": "Dimensions to group by, such as day, month, country or deviceType.",
}
FILTERS = _text(
    "filters",
    "Filters",
    "Filters as YouTube writes them, such as country==US;subscribedStatus==SUBSCRIBED.",
    maxLength=2000,
)
SORT = _text(
    "sort",
    "Sort",
    "Sort by these dimensions or metrics, - for descending, such as -views.",
    maxLength=500,
)
MAX_RESULTS = {
    "name": "max_results",
    "title": "Most rows",
    "type": "integer",
    "minimum": 1,
    "maximum": 1000000,
    "description": "The most rows to return (some reports require it, such as at most 25).",
}
CURRENCY = _text(
    "currency",
    "Currency",
    "The currency of revenue metrics, such as EUR (default USD).",
    maxLength=3,
)
CHANNEL_ID = _text(
    "channel_id",
    "Channel ID",
    "The channel; empty: the connected one (MINE). The connected account must own it.",
    maxLength=100,
)
OUTPUT = _text(
    "output",
    "Output",
    "step (default): the rows in the step output. file: a JSON workflow file with "
    "column_headers and rows, for long reports.",
    enum=["step", "file"],
)
PAGE_TOKEN = _text(
    "page_token",
    "Page token",
    "Start from this page: next_page_token of an earlier run that stopped early.",
    maxLength=1000,
)


def _report_outputs(*, to_file: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "name": "column_headers",
            "type": "array",
            "items": {"type": "object", "additionalProperties": True},
            "description": (
                "The columns: dimensions first, then metrics (name, columnType, dataType)."
            ),
        },
        {
            "name": "rows",
            "type": "array",
            "items": {"type": "array"},
            "description": "The rows, one value per column; numbers as exact decimals"
            + (" (empty with output file: they are in file)." if to_file else "."),
        },
        {"name": "row_count", "type": "integer", "description": "How many rows."},
        {
            "name": "matched_reports",
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "The reports of YouTube's channel reports page that allow this combination "
                "of dimensions, metrics and filters."
            ),
        },
    ]
    if to_file:
        rows.append(
            {
                "name": "file",
                "type": ["string", "null"],
                "value_type": "artifact_handle",
                "description": "With output file: the report as a JSON workflow file.",
            }
        )
    rows.append(WARNINGS)
    return rows


def _write(outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return outputs + PROCESSING_OUTPUTS + [WARNINGS] + EFFECT_OUTPUTS


CHECKED = (
    "Before anything is sent, the dimensions, metrics, filters, sort and max_results are "
    "checked against the report tables of YouTube's channel reports page: a combination "
    "no report allows is refused with the reason. Revenue metrics and ad performance "
    "reports need the connection type YouTube channel analytics with revenue."
)

COMPOSITES: list[dict[str, Any]] = [
    {
        "operation_id": "test_connection",
        "title": "Test connection",
        "kind": "read",
        "calls": ["GET /v2/reports"],
        "description": (
            "Checks that YouTube Analytics accepts the connection's authorization by reading "
            "the views of the connected channel (ids channel==MINE) for one day, the day "
            "before today (UTC)."
        ),
        "inputs": [],
        "outputs": [
            {
                "name": "connected",
                "type": "boolean",
                "description": "True when YouTube Analytics accepted the authorization.",
            },
            {
                "name": "connection_type",
                "type": "string",
                "description": "The connection type, which decides the Google scopes.",
            },
            {
                "name": "revenue_metrics",
                "type": "boolean",
                "description": "True when the connection type allows revenue metrics.",
            },
            {"name": "day", "type": "string", "description": "The day read, YYYY-MM-DD."},
            WARNINGS,
        ],
    },
    {
        "operation_id": "get_channel_report",
        "title": "Get channel report",
        "kind": "read",
        "calls": ["GET /v2/reports"],
        "description": (
            "Reads a YouTube Analytics report for the connected channel (or channel_id) from "
            "start_date to end_date: the metrics asked for, by the dimensions asked for, with "
            "the filters, sort and max_results given. " + CHECKED
        ),
        "inputs": [
            START,
            END,
            METRICS,
            DIMENSIONS,
            FILTERS,
            SORT,
            MAX_RESULTS,
            CURRENCY,
            CHANNEL_ID,
            OUTPUT,
        ],
        "outputs": _report_outputs(to_file=True),
    },
    {
        "operation_id": "get_video_report",
        "title": "Get video report",
        "kind": "read",
        "calls": ["GET /v2/reports"],
        "description": (
            "Reads a YouTube Analytics report for one video of the connected channel from "
            "start_date to end_date (the filter video==video_id): the metrics asked for, by "
            "the dimensions asked for, such as day or country. " + CHECKED
        ),
        "inputs": [
            _text("video_id", "Video ID", "The YouTube video ID.", maxLength=100, required=True),
            START,
            END,
            METRICS,
            DIMENSIONS,
            {**FILTERS, "description": "More filters, such as country==US (not video)."},
            SORT,
            MAX_RESULTS,
            CURRENCY,
            CHANNEL_ID,
            OUTPUT,
        ],
        "outputs": _report_outputs(to_file=True),
    },
    {
        "operation_id": "get_top_videos",
        "title": "Get top videos",
        "kind": "read",
        "calls": ["GET /v2/reports"],
        "description": (
            "Reads the connected channel's top videos from start_date to end_date (the "
            "dimension video), sorted by sort (default -views), at most max_results "
            "(default 10; YouTube allows at most 200 for these reports). " + CHECKED
        ),
        "inputs": [
            START,
            END,
            {
                **METRICS,
                "required": False,
                "description": (
                    "The metrics per video (default: " + ", ".join(TOP_VIDEO_METRICS) + ")."
                ),
            },
            {
                **SORT,
                "description": "Which metric ranks the videos, descending (default -views).",
                "enum": TOP_VIDEO_SORTS,
            },
            {
                **MAX_RESULTS,
                "maximum": 200,
                "description": "How many videos, at most 200 (default 10).",
            },
            {
                **FILTERS,
                "description": "Filters, such as country==US or subscribedStatus==SUBSCRIBED.",
            },
            CURRENCY,
            CHANNEL_ID,
        ],
        "outputs": _report_outputs(to_file=False),
    },
    {
        "operation_id": "list_groups",
        "title": "Get all my groups",
        "kind": "read",
        "calls": ["GET /v2/groups"],
        "description": (
            "Reads every YouTube Analytics group of the connected account (mine) with its "
            "title, item type and item count, page after page until all are read or "
            "max_groups; then complete is false and next_page_token says where to continue."
        ),
        "inputs": [
            {
                "name": "max_groups",
                "title": "Most groups",
                "type": "integer",
                "minimum": 1,
                "maximum": 50000,
                "description": "The most groups to read (default 5000).",
            },
            PAGE_TOKEN,
        ],
        "outputs": [
            {
                "name": "groups",
                "type": "array",
                "items": {"type": "object", "additionalProperties": True},
                "description": "The groups read.",
            },
            {"name": "count", "type": "integer", "description": "How many groups were read."},
            {
                "name": "complete",
                "type": "boolean",
                "description": "True when all groups were read.",
            },
            {
                "name": "next_page_token",
                "type": ["string", "null"],
                "description": "When complete is false: the page_token to start the next run from.",
            },
            WARNINGS,
        ],
    },
    {
        "operation_id": "create_group",
        "title": "Create group",
        "kind": "write",
        "calls": ["POST /v2/groups"],
        "description": (
            "Creates a YouTube Analytics group with a title for items of one type (default "
            "youtube#video). Returns the new group_id; add items with Add video to group."
        ),
        "inputs": [
            _text("title", "Title", "The group name.", maxLength=1000, required=True),
            _text(
                "item_type",
                "Item type",
                "What the group holds: youtube#video (default), youtube#playlist, "
                "youtube#channel or youtubePartner#asset.",
                enum=ITEM_TYPES,
            ),
        ],
        "outputs": _write(
            [
                {
                    "name": "group_id",
                    "type": ["string", "null"],
                    "description": "The new group's ID.",
                },
                {
                    "name": "data",
                    "type": ["object", "null"],
                    "additionalProperties": True,
                    "description": "The group YouTube returned.",
                },
            ]
        ),
    },
    {
        "operation_id": "add_video_to_group",
        "title": "Add video to group",
        "kind": "write",
        "calls": ["POST /v2/groupItems"],
        "description": (
            "Adds a video to a YouTube Analytics group of videos. When the video is already "
            "in the group YouTube answers HTTP 204 and the step returns already_in_group "
            "true; a full group is refused (groupContainsMaximumNumberOfItems)."
        ),
        "inputs": [
            _text("group_id", "Group ID", "The group.", maxLength=100, required=True),
            _text("video_id", "Video ID", "The YouTube video ID.", maxLength=100, required=True),
        ],
        "outputs": _write(
            [
                {
                    "name": "group_item_id",
                    "type": ["string", "null"],
                    "description": "The new group item's ID (none when it was already there).",
                },
                {
                    "name": "already_in_group",
                    "type": ["boolean", "null"],
                    "description": "True when YouTube answered that the video was already in "
                    "the group (HTTP 204).",
                },
                {
                    "name": "data",
                    "type": ["object", "null"],
                    "additionalProperties": True,
                    "description": "The group item YouTube returned.",
                },
            ]
        ),
    },
]
