"""The combination check of the report steps against YouTube's report tables."""

from __future__ import annotations

from typing import Any

import pytest

from runtime import generic, reports
from runtime.errors import ExtensionError

TABLES = generic.channel_reports()


def smallest_request(report: dict[str, Any]) -> reports.Request:
    """What a table needs at the least: its required values, one metric, size and sort."""

    def required(groups: list[dict[str, Any]]) -> list[str]:
        out: list[str] = []
        for group in groups:
            out += group["values"][: group["min"]]
        return out

    filters = {name: ["x"] for name in required(report["filters"])}
    for name, fixed in report["fixed_filters"].items():
        if name in filters:
            filters[name] = [fixed]
    sort = [report["sort_options"][0]] if report["sort_options"] else []
    if report["sort_required"] and not sort:
        sort = ["-" + report["metrics"][0]["values"][0]]
    return reports.Request(
        dimensions=required(report["dimensions"]),
        metrics=[report["metrics"][0]["values"][0]],
        filters=filters,
        sort=sort,
        max_results=report["max_results"],
    )


@pytest.mark.parametrize("report", TABLES, ids=[r["id"] for r in TABLES])
def test_every_table_allows_its_own_smallest_request(report: dict[str, Any]) -> None:
    request = smallest_request(report)
    allowed = reports.check(TABLES, request, revenue_allowed=True)
    assert report["id"] in [r["id"] for r in allowed]


def test_a_value_in_two_groups_is_counted_once() -> None:
    groups = [
        {"values": ["a", "b"], "min": 0, "max": 1},
        {"values": ["b", "c"], "min": 0, "max": 2},
    ]
    assert reports._fits(["a", "b"], groups)
    assert reports._fits(["a", "b", "c"], groups)
    assert not reports._fits(["a", "b", "c", "d"], groups)
    assert not reports._fits([], [{"values": ["a"], "min": 1, "max": 1}])


def test_filters_are_read_and_written_as_youtube_writes_them() -> None:
    parsed = reports.parse_filters("video==a,b;country==US")
    assert parsed == {"video": ["a", "b"], "country": ["US"]}
    assert reports.write_filters(parsed) == "video==a,b;country==US"
    assert reports.parse_filters(None) == {}
    for bad in ("country=US", "==US", "country==", "video==a,,b", "1x==2"):
        with pytest.raises(ExtensionError):
            reports.parse_filters(bad)


def test_sort_keys_are_names_with_an_optional_minus() -> None:
    assert reports.parse_sort("-views,day") == ["-views", "day"]
    with pytest.raises(ExtensionError):
        reports.parse_sort("views desc")


def test_a_table_that_lists_sorting_options_takes_only_those() -> None:
    city = next(r for r in TABLES if r["id"].startswith("User activity by city"))
    request = reports.Request(
        dimensions=["city"], metrics=["views"], sort=["-averageViewDuration"], max_results=10
    )
    assert reports.size_problem(city, request) == "a sort of -views, -estimatedMinutesWatched"


def test_the_monetary_metrics_are_the_starred_ones() -> None:
    paid = reports.monetary(TABLES)
    assert {"estimatedRevenue", "estimatedAdRevenue", "grossRevenue", "cpm"} <= paid
    assert "views" not in paid and "likes" not in paid
