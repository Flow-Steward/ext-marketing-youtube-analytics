"""Which combinations of dimensions, metrics and filters a channel report allows.

The rules are the report tables of YouTube's channel reports page
(https://developers.google.com/youtube/analytics/channel_reports), extracted from its
pinned copy by tests/reference/extract_channel_reports.py into runtime/registry.json
(``channel_reports``). The page says: "values from each row can be combined in an API
request as long as the combination follows the usage rules in the table" and
"Querying unsupported or mutually exclusive combinations ... causes an HTTP 400
badRequest error". So a request is sent only when at least one report table allows it:

- every dimension, metric and filter belongs to a group of that table, and each group
  holds as many of them as its usage term allows ("Required": all of them, "Optional",
  "Use exactly 1", "Use 1 or more", "Use 0 or 1", "Use 0 or more");
- a filter the table names with a value (``country==US``) has that value;
- "If you do specify multiple values for one of these filters [video, playlist], you
  can also add that filter to the list of dimensions ... even if the filter is not
  listed as a supported dimension";
- a table whose notes say "requires you to set the maxResults parameter to an integer
  value of N or less" needs max_results of at most N; one whose notes say it "also
  requires you to specify a value for the sort request parameter" needs a sort; a table
  that lists sorting options takes only those.

Revenue: "metrics marked with an asterisk (*) are monetary metrics that require this
scope [yt-analytics-monetary.readonly]", and "Ad performance reports require an
authorization token that grants access to the ... yt-analytics-monetary.readonly scope".
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from . import errors
from .errors import invalid

#: Characters of a refused value shown back in the message (our decision).
SHOWN_VALUE_LENGTH = 40
#: Alternatives a refusal lists for a metric that needs other dimensions (our decision).
LISTED_ALTERNATIVES = 5

_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
_SORT_KEY = re.compile(r"^-?[A-Za-z][A-Za-z0-9]*$")
#: The filters whose several values make them a dimension too (the page's own words).
MULTI_VALUE_DIMENSIONS = ("video", "playlist")


@dataclass
class Request:
    """What a report step asks YouTube for, as the tables name it."""

    dimensions: list[str]
    metrics: list[str]
    #: filter name -> its values (``video==a,b`` -> ``["a", "b"]``)
    filters: dict[str, list[str]] = field(default_factory=dict)
    sort: list[str] = field(default_factory=list)
    max_results: int | None = None


def parse_filters(text: str | None) -> dict[str, list[str]]:
    """``country==US;video==a,b`` -> ``{"country": ["US"], "video": ["a", "b"]}``."""
    out: dict[str, list[str]] = {}
    if not text:
        return out
    for part in text.split(";"):
        name, sep, value = part.strip().partition("==")
        if not sep or not _NAME.fullmatch(name) or not value.strip():
            raise invalid(
                "filters must be name==value pairs joined by ;, such as "
                "country==US;subscribedStatus==SUBSCRIBED"
            )
        if name in out:
            raise invalid(f"filters names {name} twice")
        values = [v.strip() for v in value.split(",")]
        if any(not v for v in values):
            raise invalid(f"filters has an empty value for {name}")
        out[name] = values
    return out


def write_filters(filters: Mapping[str, Sequence[str]]) -> str:
    return ";".join(f"{name}=={','.join(values)}" for name, values in filters.items())


def parse_sort(text: str | None) -> list[str]:
    if not text:
        return []
    keys = [k.strip() for k in text.split(",")]
    if any(not _SORT_KEY.fullmatch(k) for k in keys):
        raise invalid("sort must be dimensions or metrics joined by commas, such as -views,day")
    return keys


def names(values: Sequence[str], what: str) -> list[str]:
    out: list[str] = []
    for value in values:
        if not _NAME.fullmatch(value):
            raise invalid(
                f"{what} must be names such as views or day, not {value[:SHOWN_VALUE_LENGTH]!r}"
            )
        if value in out:
            raise invalid(f"{what} names {value} twice")
        out.append(value)
    return out


def _fits(items: Sequence[str], groups: Sequence[Mapping[str, Any]]) -> bool:
    """Whether each item can be given to one group that lists it so that every group
    holds between its ``min`` and ``max`` items."""
    choices: list[list[int]] = []
    for item in items:
        options = [i for i, g in enumerate(groups) if item in g["values"]]
        if not options:
            return False
        choices.append(options)
    counts = [0] * len(groups)
    order = sorted(range(len(items)), key=lambda i: len(choices[i]))

    def place(at: int) -> bool:
        if at == len(order):
            return all(
                groups[i]["min"] <= counts[i] <= groups[i]["max"] for i in range(len(groups))
            )
        for option in choices[order[at]]:
            if counts[option] >= groups[option]["max"]:
                continue
            counts[option] += 1
            if place(at + 1):
                return True
            counts[option] -= 1
        return False

    return place(0)


def _with_multi_value(report: Mapping[str, Any], request: Request) -> list[dict[str, Any]]:
    groups = [dict(g) for g in report["dimensions"]]
    for name in MULTI_VALUE_DIMENSIONS:
        if len(request.filters.get(name, [])) > 1 and not any(name in g["values"] for g in groups):
            groups.append({"usage": "Optional", "values": [name], "min": 0, "max": 1})
    return groups


def shape_allows(report: Mapping[str, Any], request: Request) -> bool:
    """The dimensions, metrics and filters fit the table (sort and size aside)."""
    if not _fits(request.dimensions, _with_multi_value(report, request)):
        return False
    if not _fits(request.metrics, report["metrics"]):
        return False
    if not _fits(list(request.filters), report["filters"]):
        return False
    for name, fixed in report["fixed_filters"].items():
        if name in request.filters and request.filters[name] != [fixed]:
            return False
    return True


def size_problem(report: Mapping[str, Any], request: Request) -> str | None:
    """What the table needs of sort and max_results that the request lacks, or None."""
    needs: list[str] = []
    limit = report["max_results"]
    if limit is not None and (request.max_results is None or request.max_results > limit):
        needs.append(f"max_results of at most {limit}")
    if report["sort_required"] and not request.sort:
        needs.append("a sort")
    options = report["sort_options"]
    if options and request.sort and any(k not in options for k in request.sort):
        needs.append("a sort of " + ", ".join(options))
    return " and ".join(needs) if needs else None


def matching(
    reports: Sequence[Mapping[str, Any]], request: Request
) -> tuple[list[Mapping[str, Any]], list[str]]:
    """The tables that allow the request, and what the tables that allow its shape need."""
    allowed: list[Mapping[str, Any]] = []
    needs: list[str] = []
    for report in reports:
        if not shape_allows(report, request):
            continue
        problem = size_problem(report, request)
        if problem is None:
            allowed.append(report)
        else:
            needs.append(f"{report['id']}: {problem}")
    return allowed, needs


def monetary(reports: Sequence[Mapping[str, Any]]) -> frozenset[str]:
    return frozenset(m for r in reports for m in r["monetary_metrics"])


def check(
    reports: Sequence[Mapping[str, Any]], request: Request, *, revenue_allowed: bool
) -> list[Mapping[str, Any]]:
    """The tables that allow the request; refuses (nothing sent) when none does."""
    known_metrics = {m for r in reports for g in r["metrics"] for m in g["values"]}
    unknown = [m for m in request.metrics if m not in known_metrics]
    if unknown:
        raise invalid(
            "No channel report of YouTube's report tables has the metrics "
            + ", ".join(unknown[: errors.LISTED_NAMES])
        )
    allowed, needs = matching(reports, request)
    if not allowed:
        if needs:
            raise invalid(
                "YouTube's channel report tables allow these dimensions, metrics and filters "
                "only with " + "; or ".join(needs[:LISTED_ALTERNATIVES])
            )
        what = f"dimensions [{', '.join(request.dimensions) or 'none'}]"
        what += f", metrics [{', '.join(request.metrics)}]"
        what += f" and filters [{', '.join(request.filters) or 'none'}]"
        raise invalid(
            f"No report of YouTube's channel report tables allows {what}; YouTube refuses such "
            "a query (The query is not supported)"
        )
    if not revenue_allowed:
        paid = sorted(set(request.metrics) & monetary(reports))
        if paid:
            raise invalid(
                "Revenue metrics ("
                + ", ".join(paid[: errors.LISTED_NAMES])
                + ") need the Google scope "
                "yt-analytics-monetary.readonly: use a connection of the type YouTube channel "
                "analytics with revenue"
            )
        if all(r["monetary_scope_required"] for r in allowed):
            raise invalid(
                "Ad performance reports need the Google scope yt-analytics-monetary.readonly: "
                "use a connection of the type YouTube channel analytics with revenue"
            )
    return allowed


__all__ = [
    "MULTI_VALUE_DIMENSIONS",
    "Request",
    "check",
    "matching",
    "monetary",
    "names",
    "parse_filters",
    "parse_sort",
    "shape_allows",
    "size_problem",
    "write_filters",
]
