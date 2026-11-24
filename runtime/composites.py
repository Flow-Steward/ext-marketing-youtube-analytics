"""The everyday steps, built on the generated steps of runtime/registry.json.

Each one goes through the same checks and transport as the generated step of the method
it calls (generic.prepare / generic.to_call), so documented parameters, refusals and
the token handling are the same. The report steps first check the combination of
dimensions, metrics and filters against YouTube's channel report tables
(runtime/reports.py), so a query YouTube would refuse is not sent. Lists read every page
(runtime/pages.py). Writes go through the one outcome table (runtime/outcome.py); the
steps that create something (Create group, Add video to group) are of the class that
needs the new id from YouTube's answer.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta, timezone
from typing import Any

from . import errors, files, generic, outcome, pages, reports
from .context import Context
from .errors import invalid
from .params import integer, text
from .transport import Answer, Call, dumps_json

#: GroupContentDetails.itemType: "Valid values for this property are: youtube#channel,
#: youtube#playlist, youtube#video, youtubePartner#asset".
ITEM_TYPES = ["youtube#video", "youtube#playlist", "youtube#channel", "youtubePartner#asset"]
#: The metrics Get top videos asks for when none are given.
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
#: "These reports require you to set the maxResults parameter to an integer value of 200
#: or less" (Top videos, channel reports page).
TOP_VIDEOS_MAX = 200
TOP_VIDEOS_DEFAULT = 10
MAX_TITLE = 1000
_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REPORT_SHOWN = "GET /v2/reports"
REPORT_INPUTS = {
    "start_date",
    "end_date",
    "metrics",
    "dimensions",
    "filters",
    "sort",
    "max_results",
    "currency",
    "channel_id",
    "output",
}


# -- helpers -----------------------------------------------------------------------------


def _closed(given: Mapping[str, Any], allowed: set[str]) -> dict[str, Any]:
    rest = {k: v for k, v in given.items() if k != "connection_ref"}
    unknown = sorted(set(rest) - allowed)
    if unknown:
        raise invalid(f"The step input has unknown fields: {', '.join(unknown[:10])}")
    return rest


def _read(context: Context, operation_id: str, given: Mapping[str, Any]) -> Any:
    """One read through a generated step; its JSON value."""
    entry = generic.spec(operation_id)
    plan = generic.prepare(operation_id, given)
    answer = context.transport.read(generic.to_call(entry, plan))
    return generic._read_json(context, answer, plan.shown)


def _ident(value: Any, name: str) -> str:
    """A YouTube id: letters, digits, - and _ (at most 100)."""
    result = text(value, name, max_length=100)
    if any(ch not in _ID_CHARS for ch in result):
        raise invalid(f"{name} must be a YouTube ID (letters, digits, - and _)")
    return result


def _opt_int(given: Mapping[str, Any], name: str, *, default: int, low: int, high: int) -> int:
    value = given.get(name)
    if value is None or value == "":
        return default
    return integer({"minimum": low, "maximum": high}, value, name)


def _opt_text(given: Mapping[str, Any], name: str, *, max_length: int) -> str | None:
    value = given.get(name)
    if value is None or value == "":
        return None
    return text(value, name, max_length=max_length)


def _choice(given: Mapping[str, Any], name: str, allowed: list[str], default: str | None) -> Any:
    value = given.get(name)
    if value is None or value == "":
        return default
    if value not in allowed:
        raise invalid(f"{name} must be one of: {', '.join(allowed)}")
    return value


def _list(given: Mapping[str, Any], name: str, *, max_items: int, max_length: int) -> list[str]:
    value = given.get(name)
    if value is None or value == [] or value == "":
        return []
    if not isinstance(value, list) or len(value) > max_items:
        raise invalid(f"{name} must be a list of at most {max_items} values")
    return [text(v, f"{name} item {i}", max_length=max_length) for i, v in enumerate(value, 1)]


def _output_choice(given: Mapping[str, Any]) -> bool:
    value = given.get("output")
    if value in (None, "", "step"):
        return False
    if value == "file":
        return True
    raise invalid("output must be step or file")


def _day(given: Mapping[str, Any], name: str) -> date:
    value = text(given.get(name), name, max_length=10)
    if not _DAY.fullmatch(value):
        raise invalid(f"{name} must be a date written YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise invalid(f"{name} is not a real date: {value}") from None


def _period(given: Mapping[str, Any]) -> tuple[date, date]:
    start = _day(given, "start_date")
    end = _day(given, "end_date")
    if end < start:
        raise invalid("end_date may not be before start_date")
    return start, end


def _ids(given: Mapping[str, Any]) -> str:
    channel = given.get("channel_id")
    return "channel==MINE" if channel in (None, "") else f"channel=={_ident(channel, 'channel_id')}"


def _currency(given: Mapping[str, Any]) -> str | None:
    currency = _opt_text(given, "currency", max_length=3)
    if currency is not None and (
        len(currency) != 3 or not currency.isalpha() or not currency.isupper()
    ):
        raise invalid("currency must be a three-letter code such as EUR")
    return currency


def _max_results(given: Mapping[str, Any], *, high: int = 1_000_000) -> int | None:
    if given.get("max_results") in (None, ""):
        return None
    return integer({"minimum": 1, "maximum": high}, given["max_results"], "max_results")


# -- test connection ---------------------------------------------------------------------


def _yesterday() -> date:
    return datetime.now(timezone.utc).date() - timedelta(days=1)


def test_connection(context: Context) -> dict[str, Any]:
    _closed(context.operation_input, set())
    day = _yesterday().isoformat()
    data = _read(
        context,
        "query_analytics_report",
        {"ids": "channel==MINE", "start_date": day, "end_date": day, "metrics": "views"},
    )
    _table(context, data)
    return {
        "connected": True,
        "connection_type": context.connection.connection_type,
        "revenue_metrics": context.connection.revenue,
        "day": day,
        "warnings": [],
    }


#: The channel of the authorization: YouTube Data API v3 channels.list (mine=true), allowed
#: by the youtube.readonly scope every connection type asks for.
CHANNELS_SHOWN = "GET /youtube/v3/channels"


def verify_identity(context: Context) -> dict[str, Any]:
    """The post-connect action: which YouTube channel the authorization is for."""
    _closed(context.operation_input, set())
    call = Call(
        method="GET",
        path="/youtube/v3/channels",
        shown=CHANNELS_SHOWN,
        api="data",
        query=(("part", "id,snippet"), ("mine", "true")),
    )
    data = generic._read_json(context, context.transport.read(call), CHANNELS_SHOWN)
    if not isinstance(data, Mapping) or not isinstance(data.get("items"), list):
        raise pages.bad(CHANNELS_SHOWN, "has no items list")
    if not data["items"]:
        raise errors.no_effect(errors.NOT_FOUND, "YouTube found no channel for this Google account")
    item = data["items"][0]
    if not isinstance(item, Mapping) or not isinstance(item.get("id"), str) or not item["id"]:
        raise pages.bad(CHANNELS_SHOWN, "carries no channel id")
    snippet = item.get("snippet")
    title = snippet.get("title") if isinstance(snippet, Mapping) else None
    return {
        "subject": errors.safe_text(item["id"], 100),
        "verified_display_name": errors.safe_text(title, 200) if isinstance(title, str) else None,
        "health": "ok",
    }


# -- reports -----------------------------------------------------------------------------


def _table(context: Context, data: Any) -> tuple[list[Any], list[Any]]:
    """The column headers and rows of a report answer."""
    if not isinstance(data, Mapping):
        raise pages.bad(REPORT_SHOWN, "is not a JSON object")
    generic.refuse_failed_report(context, data, REPORT_SHOWN)
    headers = data.get("columnHeaders", [])
    rows = data.get("rows", [])
    if headers is None:
        headers = []
    if rows is None:
        rows = []
    if not isinstance(headers, list) or not isinstance(rows, list):
        raise pages.bad(REPORT_SHOWN, "has columnHeaders or rows that are not lists")
    if any(not isinstance(row, list) for row in rows):
        raise pages.bad(REPORT_SHOWN, "has a row that is not a list")
    return headers, rows


def plan_report(
    given: Mapping[str, Any],
    *,
    dimensions: list[str],
    metrics: list[str],
    filters: dict[str, list[str]],
    sort: list[str],
    max_results: int | None,
    revenue: bool,
) -> tuple[dict[str, Any], list[str]]:
    """The checked query of a report step and the names of the tables that allow it."""
    start, end = _period(given)
    request = reports.Request(
        dimensions=reports.names(dimensions, "dimensions"),
        metrics=reports.names(metrics, "metrics"),
        filters=filters,
        sort=sort,
        max_results=max_results,
    )
    allowed = reports.check(generic.channel_reports(), request, revenue_allowed=revenue)
    query: dict[str, Any] = {
        "ids": _ids(given),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "metrics": ",".join(request.metrics),
    }
    if request.dimensions:
        query["dimensions"] = ",".join(request.dimensions)
    if filters:
        query["filters"] = reports.write_filters(filters)
    if sort:
        query["sort"] = ",".join(sort)
    if max_results is not None:
        query["max_results"] = max_results
    currency = _currency(given)
    if currency:
        query["currency"] = currency
    return query, [str(r["id"]) for r in allowed]


def _run_report(
    context: Context, query: dict[str, Any], matched: list[str], *, to_file: bool
) -> dict[str, Any]:
    data = _read(context, "query_analytics_report", query)
    headers, rows = _table(context, data)
    result: dict[str, Any] = {
        "column_headers": headers,
        "rows": rows,
        "row_count": len(rows),
        "matched_reports": matched,
    }
    if to_file:
        handle = None
        if rows or headers:
            handle = files.save(
                context,
                dumps_json({"column_headers": headers, "rows": rows}).encode("utf-8"),
                content_type="application/json",
                what="The report",
            )
        result["rows"] = []
        result["file"] = handle
    result["warnings"] = []
    return result


def _channel_plan(given: Mapping[str, Any], revenue: bool) -> tuple[dict[str, Any], list[str]]:
    metrics = _list(given, "metrics", max_items=50, max_length=100)
    if not metrics:
        raise invalid("metrics is required: one or more YouTube Analytics metrics, such as views")
    return plan_report(
        given,
        dimensions=_list(given, "dimensions", max_items=10, max_length=100),
        metrics=metrics,
        filters=reports.parse_filters(_opt_text(given, "filters", max_length=2000)),
        sort=reports.parse_sort(_opt_text(given, "sort", max_length=500)),
        max_results=_max_results(given),
        revenue=revenue,
    )


def get_channel_report(context: Context) -> dict[str, Any]:
    given = _closed(context.operation_input, REPORT_INPUTS)
    query, matched = _channel_plan(given, context.connection.revenue)
    return _run_report(context, query, matched, to_file=_output_choice(given))


def _video_plan(given: Mapping[str, Any], revenue: bool) -> tuple[dict[str, Any], list[str]]:
    video = _ident(given.get("video_id"), "video_id")
    metrics = _list(given, "metrics", max_items=50, max_length=100)
    if not metrics:
        raise invalid("metrics is required: one or more YouTube Analytics metrics, such as views")
    more = reports.parse_filters(_opt_text(given, "filters", max_length=2000))
    if "video" in more or "group" in more:
        raise invalid("filters may not name video or group: video_id chooses the video")
    return plan_report(
        given,
        dimensions=_list(given, "dimensions", max_items=10, max_length=100),
        metrics=metrics,
        filters={"video": [video], **more},
        sort=reports.parse_sort(_opt_text(given, "sort", max_length=500)),
        max_results=_max_results(given),
        revenue=revenue,
    )


def get_video_report(context: Context) -> dict[str, Any]:
    given = _closed(context.operation_input, REPORT_INPUTS | {"video_id"})
    query, matched = _video_plan(given, context.connection.revenue)
    return _run_report(context, query, matched, to_file=_output_choice(given))


TOP_INPUTS = {
    "start_date",
    "end_date",
    "metrics",
    "sort",
    "max_results",
    "filters",
    "currency",
    "channel_id",
}


def _top_plan(given: Mapping[str, Any], revenue: bool) -> tuple[dict[str, Any], list[str]]:
    metrics = _list(given, "metrics", max_items=50, max_length=100) or list(TOP_VIDEO_METRICS)
    sort = _choice(given, "sort", TOP_VIDEO_SORTS, "-views")
    more = reports.parse_filters(_opt_text(given, "filters", max_length=2000))
    if "video" in more or "group" in more:
        raise invalid("filters may not name video or group for the top videos")
    return plan_report(
        given,
        dimensions=["video"],
        metrics=metrics,
        filters=more,
        sort=[sort],
        max_results=_opt_int(
            given, "max_results", default=TOP_VIDEOS_DEFAULT, low=1, high=TOP_VIDEOS_MAX
        ),
        revenue=revenue,
    )


def get_top_videos(context: Context) -> dict[str, Any]:
    given = _closed(context.operation_input, TOP_INPUTS)
    query, matched = _top_plan(given, context.connection.revenue)
    return _run_report(context, query, matched, to_file=False)


# -- groups ------------------------------------------------------------------------------


def list_groups(context: Context) -> dict[str, Any]:
    given = _closed(context.operation_input, {"max_groups", "page_token"})
    entry = generic.spec("get_analytics_groups")
    pager = entry["pager"]

    def fetch(token: str | None, limit: int) -> Any:
        _ = limit  # groups.list has no page size: pages are taken whole
        query: dict[str, Any] = {"mine": True}
        if token is not None:
            query[pager["token_input"]] = token
        return _read(context, "get_analytics_groups", query)

    return pages.collect(
        context,
        fetch=fetch,
        shown=f"{entry['method']} {entry['path']}",
        start=_opt_text(given, "page_token", max_length=pages.MAX_TOKEN),
        page_size=1,
        smallest=1,
        most=_opt_int(given, "max_groups", default=5000, low=1, high=50_000),
        to_file=False,
        out_key="groups",
    )


def _write(
    context: Context,
    operation_id: str,
    given: Mapping[str, Any],
    *,
    step: str = outcome.OTHER,
    what: str = "resource",
) -> dict[str, Any]:
    """One write through a generated step, its outcome by table T."""
    entry = generic.spec(operation_id)
    plan = generic.prepare(operation_id, given)
    answer = context.transport.write(generic.to_call(entry, plan))
    return _outcome(context, entry, answer, plan.shown, step=step, what=what)


def _outcome(
    context: Context,
    entry: Mapping[str, Any],
    answer: Answer,
    shown: str,
    *,
    step: str,
    what: str,
) -> dict[str, Any]:
    return outcome.write_outcome(
        context,
        answer,
        shown,
        entry=entry,
        promised=entry["answer"] == "json",
        step=step,
        find_id=outcome.resource_id,
        what=what,
    )


GROUP_INPUTS = {"title", "item_type"}


def _group_body(given: Mapping[str, Any]) -> dict[str, Any]:
    title = text(given.get("title"), "title", max_length=MAX_TITLE)
    item_type = _choice(given, "item_type", ITEM_TYPES, "youtube#video")
    return {"snippet": {"title": title}, "contentDetails": {"itemType": item_type}}


def validate_create_group(given: Mapping[str, Any]) -> None:
    _group_body(_closed(given, GROUP_INPUTS))


def create_group(context: Context) -> dict[str, Any]:
    given = _closed(context.operation_input, GROUP_INPUTS)
    body = _group_body(given)
    out = _write(
        context, "create_analytics_group", {"body": body}, step=outcome.CREATE, what="group"
    )
    return {
        "group_id": out["id"],
        "data": out["data"],
        "processing": out["processing"],
        "applied": out["applied"],
        "check": out["check"],
        "warnings": out["warnings"],
    }


ADD_INPUTS = {"group_id", "video_id"}


def _add_body(given: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "groupId": _ident(given.get("group_id"), "group_id"),
        "resource": {"kind": "youtube#video", "id": _ident(given.get("video_id"), "video_id")},
    }


def validate_add_video_to_group(given: Mapping[str, Any]) -> None:
    _add_body(_closed(given, ADD_INPUTS))


def add_video_to_group(context: Context) -> dict[str, Any]:
    given = _closed(context.operation_input, ADD_INPUTS)
    body = _add_body(given)
    entry = generic.spec("add_analytics_group_item")
    plan = generic.prepare("add_analytics_group_item", {"body": body})
    answer = context.transport.write(generic.to_call(entry, plan))
    if answer.status == 204:
        # groupItems.insert: "If the item specified in the request had already been
        # included in the group before the request was made, this method returns an HTTP
        # 204 response code (No Content)."
        facts = outcome.processing_of(entry, answer.status)
        return {
            "group_item_id": None,
            "already_in_group": True,
            "data": None,
            **facts,
            "warnings": [],
        }
    out = _outcome(context, entry, answer, plan.shown, step=outcome.CREATE, what="group item")
    return {
        "group_item_id": out["id"],
        "already_in_group": False,
        "data": out["data"],
        "processing": out["processing"],
        "applied": out["applied"],
        "check": out["check"],
        "warnings": out["warnings"],
    }


#: Everyday step id -> runner.
COMPOSITES: dict[str, Callable[[Context], dict[str, Any]]] = {
    "test_connection": test_connection,
    "get_channel_report": get_channel_report,
    "get_video_report": get_video_report,
    "get_top_videos": get_top_videos,
    "list_groups": list_groups,
    "create_group": create_group,
    "add_video_to_group": add_video_to_group,
    "verify_identity": verify_identity,
}
#: Everyday steps that change data in YouTube Analytics.
COMPOSITE_WRITES: frozenset[str] = frozenset({"create_group", "add_video_to_group"})
#: Input checks of the writes, run before anything is sent and in a test run.
VALIDATORS: dict[str, Callable[[Mapping[str, Any]], None]] = {
    "create_group": validate_create_group,
    "add_video_to_group": validate_add_video_to_group,
}
#: The outputs of each write in a test run (besides the effect facts).
NEUTRAL: dict[str, dict[str, Any]] = {
    "create_group": {"group_id": None, "data": None},
    "add_video_to_group": {"group_item_id": None, "already_in_group": None, "data": None},
}

__all__ = ["COMPOSITES", "COMPOSITE_WRITES", "NEUTRAL", "VALIDATORS"]
