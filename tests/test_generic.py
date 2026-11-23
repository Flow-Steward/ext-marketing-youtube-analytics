"""The generated steps: inputs checked from the source, requests, answers and lists."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl

import pytest
from support import TOKEN, FakeYouTube, ok, raw, refuse, run, text_of

from runtime import budget, generic

REGISTRY = generic.registry()
REPORT_INPUT = {
    "ids": "channel==MINE",
    "start_date": "2026-01-01",
    "end_date": "2026-01-31",
    "metrics": "views",
}


def minimal_input(entry: dict[str, Any]) -> dict[str, Any]:
    """The smallest valid input of a generated step."""
    given: dict[str, Any] = {}
    for prm in entry["path_params"]:
        given[prm["input"]] = "x1"
    for prm in entry["query"]:
        n = prm["node"]
        if not n["required"]:
            continue
        if n["kind"] == "text_list":
            given[prm["input"]] = [n["allowed"][0]] if n.get("allowed") else ["snippet"]
        elif n["kind"] == "integer":
            given[prm["input"]] = n.get("minimum", 1)
        elif n["kind"] == "boolean":
            given[prm["input"]] = True
        elif n.get("allowed"):
            given[prm["input"]] = n["allowed"][-1]
        elif n.get("format") == "date":
            given[prm["input"]] = "2026-01-01"
        elif n.get("format") == "date-time":
            given[prm["input"]] = "2026-01-01T00:00:00Z"
        else:
            given[prm["input"]] = "x1"
    body = entry["body"]
    if body and body["required"]:
        given["body"] = {body["json"]["properties"][0]: "x"}
    return given


@pytest.mark.parametrize("operation_id", sorted(REGISTRY))
def test_every_generated_step_accepts_its_minimal_input(operation_id: str) -> None:
    entry = REGISTRY[operation_id]
    plan = generic.prepare(operation_id, minimal_input(entry))
    assert plan.method == entry["method"]
    assert "{" not in plan.path


@pytest.mark.parametrize("operation_id", sorted(REGISTRY))
def test_every_generated_step_refuses_unknown_inputs(operation_id: str) -> None:
    given = {**minimal_input(REGISTRY[operation_id]), "nonsense_field": 1}
    result = run(operation_id, given, FakeYouTube())
    assert result["error_code"] == "invalid_payload"
    assert "nonsense_field" in result["error"]
    assert result["definitely_no_external_effect"] is True


def test_the_query_is_sent_as_the_source_names_it() -> None:
    fake = FakeYouTube(ok({"columnHeaders": [], "rows": []}))
    given = {**REPORT_INPUT, "dimensions": "day", "max_results": 5, "start_index": 2}
    result = run("query_analytics_report", given, fake)
    assert result["ok"] is True, result
    assert sorted(fake.calls[0].query) == sorted(
        [
            ("ids", "channel==MINE"),
            ("startDate", "2026-01-01"),
            ("endDate", "2026-01-31"),
            ("metrics", "views"),
            ("dimensions", "day"),
            ("maxResults", "5"),
            ("startIndex", "2"),
        ]
    )


@pytest.mark.parametrize(
    ("given", "message"),
    [
        ({**REPORT_INPUT, "start_index": 0}, "from 1"),
        ({**REPORT_INPUT, "max_results": "x"}, "whole number"),
        ({**REPORT_INPUT, "ids": "a\x00b"}, "control characters"),
        ({k: v for k, v in REPORT_INPUT.items() if k != "metrics"}, "metrics is required"),
        ({k: v for k, v in REPORT_INPUT.items() if k != "ids"}, "ids is required"),
    ],
)
def test_query_values_are_checked_against_the_source(given: dict[str, Any], message: str) -> None:
    fake = FakeYouTube()
    result = run("query_analytics_report", given, fake)
    assert result["error_code"] == "invalid_payload", result
    assert message in result["error"]
    assert fake.calls == []


@pytest.mark.parametrize("value", ["2026-02-30", "2026-1-01", "20260101"])
def test_an_impossible_analytics_date_is_refused(value: str) -> None:
    given = {
        "ids": "channel==MINE",
        "start_date": value,
        "end_date": "2026-03-01",
        "metrics": "views",
    }
    result = run("query_analytics_report", given, FakeYouTube())
    assert result["error_code"] == "invalid_payload"


def test_the_analytics_required_parameters_come_from_the_source_text() -> None:
    query = {p["name"]: p["node"]["required"] for p in REGISTRY["query_analytics_report"]["query"]}
    assert query["startDate"] and query["endDate"] and query["metrics"] and query["ids"]
    assert not query["dimensions"]


def test_a_body_with_fields_the_resource_does_not_have_is_refused() -> None:
    fake = FakeYouTube()
    result = run("update_analytics_group", {"body": {"id": "G1", "colour": "red"}}, fake)
    assert result["error_code"] == "invalid_payload"
    assert "colour" in result["error"] and "Group" in result["error"]
    assert fake.calls == []


def test_a_required_body_is_required() -> None:
    result = run("update_analytics_group", {}, FakeYouTube())
    assert result["error_code"] == "invalid_payload" and "body is required" in result["error"]


def test_the_body_is_sent_as_json() -> None:
    fake = FakeYouTube(ok({"id": "G1"}))
    run("update_analytics_group", {"body": {"id": "G1", "snippet": {"title": "T"}}}, fake)
    call = fake.calls[0]
    assert call.verb == "PUT" and call.body == {"id": "G1", "snippet": {"title": "T"}}
    assert call.headers["content-type"] == "application/json"
    assert call.host == "youtubeanalytics.googleapis.com" and call.path == "/v2/groups"


def test_a_deletion_answered_without_content_answers_with_no_data() -> None:
    fake = FakeYouTube(raw(204, b""))
    result = run("delete_analytics_group", {"id": "G1"}, fake)
    assert result["ok"] is True and result["result"]["data"] is None
    assert result["result"]["processing"] == "completed"
    assert fake.calls[0].verb == "DELETE" and dict(fake.calls[0].query) == {"id": "G1"}


def test_group_items_are_read_for_a_group() -> None:
    fake = FakeYouTube(ok({"items": [{"id": "i1"}]}))
    result = run("get_analytics_group_items", {"group_id": "G1"}, fake)
    assert result["ok"] is True and result["result"]["data"]["items"] == [{"id": "i1"}]
    assert dict(fake.calls[0].query) == {"groupId": "G1"}


# -- lists ---------------------------------------------------------------------------------


def page(ids: list[str], token: str | None = None, **extra: Any) -> Any:
    body: dict[str, Any] = {"kind": "x#list", "items": [{"id": i} for i in ids], **extra}
    if token:
        body["nextPageToken"] = token
    return ok(body)


def test_one_page_returns_items_and_where_to_continue() -> None:
    fake = FakeYouTube(page(["a", "b"], "T2", etag="e"))
    result = run("get_analytics_groups", {"mine": True}, fake)
    out = result["result"]
    assert out["items"] == [{"id": "a"}, {"id": "b"}] and out["count"] == 2
    assert out["complete"] is False and out["next_page_token"] == "T2"
    assert out["data"] == {"kind": "x#list", "etag": "e"}


def test_all_pages_follows_the_tokens_to_the_end() -> None:
    fake = FakeYouTube(page(["a"], "T2"), page(["b"], "T3"), page(["c"]))
    result = run("get_analytics_groups", {"mine": True, "all_pages": True}, fake)
    out = result["result"]
    assert [i["id"] for i in out["items"]] == ["a", "b", "c"]
    assert out["complete"] is True and out["next_page_token"] is None
    assert [dict(c.query).get("pageToken") for c in fake.calls] == [None, "T2", "T3"]
    # groups.list has no page size: pages are taken whole.
    assert all("maxResults" not in dict(c.query) for c in fake.calls)


def test_max_items_needs_all_pages() -> None:
    result = run("get_analytics_groups", {"mine": True, "max_items": 5}, FakeYouTube())
    assert result["error_code"] == "invalid_payload"


def test_all_pages_stops_at_max_items_on_whole_pages() -> None:
    fake = FakeYouTube(page(["a", "b"], "T2"), page(["c", "d"], "T3"))
    given = {"mine": True, "all_pages": True, "max_items": 3}
    out = run("get_analytics_groups", given, fake)["result"]
    assert [i["id"] for i in out["items"]] == ["a", "b", "c", "d"]
    assert out["complete"] is False and out["next_page_token"] == "T3"


def test_all_pages_starts_from_the_page_token_given() -> None:
    fake = FakeYouTube(page(["c"]))
    run("get_analytics_groups", {"mine": True, "all_pages": True, "page_token": "T3"}, fake)
    assert dict(fake.calls[0].query)["pageToken"] == "T3"


def test_an_empty_page_with_a_next_token_does_not_end_the_list() -> None:
    fake = FakeYouTube(page([], "T2"), page(["a"]))
    out = run("get_analytics_groups", {"mine": True, "all_pages": True}, fake)["result"]
    assert out["complete"] is True and out["count"] == 1 and len(fake.calls) == 2


def test_a_token_sent_twice_is_an_incomplete_read() -> None:
    fake = FakeYouTube(page(["a"], "T2"), page(["b"], "T2"))
    result = run("get_analytics_groups", {"mine": True, "all_pages": True}, fake)
    assert result["error_code"] == "invalid_response"
    assert "not complete" in result["error"]


def test_duplicates_are_returned_once_with_a_warning() -> None:
    fake = FakeYouTube(page(["a", "b"], "T2"), page(["b", "c"]))
    out = run("get_analytics_groups", {"mine": True, "all_pages": True}, fake)["result"]
    assert [i["id"] for i in out["items"]] == ["a", "b", "c"]
    assert "appeared twice" in out["warnings"][0]


def test_a_failure_after_the_first_page_returns_what_was_read() -> None:
    fake = FakeYouTube(page(["a"], "T2"), refuse(503, b""))
    out = run("get_analytics_groups", {"mine": True, "all_pages": True}, fake)
    assert out["ok"] is True
    result = out["result"]
    assert result["count"] == 1 and result["complete"] is False
    assert result["next_page_token"] == "T2"
    assert "page_token T2" in result["warnings"][-1]


def test_a_failure_on_the_first_page_fails_the_step() -> None:
    fake = FakeYouTube(refuse(503, b""))
    result = run("get_analytics_groups", {"mine": True, "all_pages": True}, fake)
    assert result["ok"] is False and result["error_code"] == "upstream_failure"


def test_a_full_output_stops_with_the_token_of_the_page_not_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(budget, "MAX_SERIALIZED_BYTES", 5000)
    big = "x" * 1200
    fake = FakeYouTube(
        ok({"items": [{"id": "a", "t": big}], "nextPageToken": "T2"}),
        ok({"items": [{"id": "b", "t": big}], "nextPageToken": "T3"}),
        ok({"items": [{"id": "c", "t": big}], "nextPageToken": "T4"}),
    )
    result = run("get_analytics_groups", {"mine": True, "all_pages": True}, fake)
    assert result["ok"] is True, result
    out = result["result"]
    assert [i["id"] for i in out["items"]] == ["a", "b"]
    assert out["complete"] is False and out["next_page_token"] == "T3"
    assert budget.fits(out)


def test_a_first_page_that_does_not_fit_fails_the_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(budget, "MAX_SERIALIZED_BYTES", 5000)
    fake = FakeYouTube(ok({"items": [{"id": i, "t": "x" * 1200} for i in "abcd"]}))
    result = run("get_analytics_groups", {"mine": True, "all_pages": True}, fake)
    assert result["error_code"] == "response_too_large"
    assert result["definitely_no_external_effect"] is True


@pytest.mark.parametrize("operation_id", sorted(k for k, v in REGISTRY.items() if v["pager"]))
def test_every_list_step_offers_all_pages(operation_id: str) -> None:
    names = generic.inputs_of(REGISTRY[operation_id])
    assert {"all_pages", "max_items", "page_token"} <= names
    assert operation_id == "get_analytics_groups"


def test_a_read_returns_no_token_in_its_output() -> None:
    fake = FakeYouTube(page(["a"], extra=TOKEN))
    result = run("get_analytics_groups", {"mine": True}, fake)
    assert TOKEN not in text_of(result)


def test_query_strings_are_url_encoded() -> None:
    fake = FakeYouTube(ok({"columnHeaders": [], "rows": []}))
    run("query_analytics_report", {**REPORT_INPUT, "filters": "video==a,b;country==US"}, fake)
    assert ("filters", "video==a,b;country==US") in parse_qsl(fake.calls[0].url.split("?", 1)[1])
