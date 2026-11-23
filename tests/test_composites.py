"""The everyday steps."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest
from support import Artifacts, FakeYouTube, google_error, ok, raw, refuse, run

from runtime import composites

PERIOD = {"start_date": "2026-01-01", "end_date": "2026-01-31"}
MONETARY = "youtube_analytics_channel_monetary"


def table(*names: str, rows: list[list[Any]] | None = None) -> Any:
    return ok(
        {
            "kind": "youtubeAnalytics#resultTable",
            "columnHeaders": [{"name": n} for n in names],
            "rows": rows or [],
        }
    )


def query_of(fake: FakeYouTube, index: int = 0) -> dict[str, str]:
    return dict(fake.calls[index].query)


# -- connection ------------------------------------------------------------------------------


def test_test_connection_reads_a_day_of_views() -> None:
    fake = FakeYouTube(table("views", rows=[[3]]))
    out = run("test_connection", {}, fake)["result"]
    assert out["connected"] is True
    assert out["connection_type"] == "youtube_analytics_channel"
    assert out["revenue_metrics"] is False and out["warnings"] == []
    assert fake.calls[0].path == "/v2/reports"


def test_the_post_connect_action_names_the_channel() -> None:
    fake = FakeYouTube(ok({"items": [{"id": "UC1", "snippet": {"title": "My channel"}}]}))
    out = run("verify_identity", {}, fake)["result"]
    assert out == {"subject": "UC1", "verified_display_name": "My channel", "health": "ok"}
    assert fake.calls[0].host == "www.googleapis.com"
    assert fake.calls[0].path == "/youtube/v3/channels"
    assert ("mine", "true") in fake.calls[0].query


def test_the_post_connect_action_without_a_channel_is_not_found() -> None:
    result = run("verify_identity", {}, FakeYouTube(ok({"items": []})))
    assert result["ok"] is False and result["error_code"] == "not_found"


def test_test_connection_refused_by_google_is_an_authentication_failure() -> None:
    fake = FakeYouTube(refuse(403, google_error(403, "forbidden", "Forbidden")))
    result = run("test_connection", {}, fake)
    assert result["error_code"] == "authentication_failed"


# -- channel report -----------------------------------------------------------------------------


def test_a_channel_report_by_day_with_exact_numbers() -> None:
    body = (
        b'{"kind":"youtubeAnalytics#resultTable","columnHeaders":[{"name":"day"},'
        b'{"name":"views"},{"name":"averageViewPercentage"}],"rows":[["2026-01-01",5,41.2345]]}'
    )
    fake = FakeYouTube(raw(200, body))
    result = run(
        "get_channel_report",
        {**PERIOD, "metrics": ["views", "averageViewPercentage"], "dimensions": ["day"]},
        fake,
    )
    assert result["ok"] is True, result
    out = result["result"]
    assert out["rows"] == [["2026-01-01", 5, "41.2345"]] and out["row_count"] == 1
    assert Decimal(out["rows"][0][2]) == Decimal("41.2345")
    assert "User activity by country for specific time periods" in out["matched_reports"]
    query = query_of(fake)
    assert query == {
        "ids": "channel==MINE",
        "startDate": "2026-01-01",
        "endDate": "2026-01-31",
        "metrics": "views,averageViewPercentage",
        "dimensions": "day",
    }
    assert fake.calls[0].host == "youtubeanalytics.googleapis.com"


def test_a_channel_report_of_another_channel_with_filters_sort_and_currency() -> None:
    fake = FakeYouTube(table("country", "views"))
    given = {
        **PERIOD,
        "metrics": ["views"],
        "dimensions": ["country"],
        "filters": "continent==150",
        "sort": "-views",
        "max_results": 10,
        "currency": "EUR",
        "channel_id": "UC123",
    }
    result = run("get_channel_report", given, fake)
    assert result["ok"] is True, result
    query = query_of(fake)
    assert query["ids"] == "channel==UC123" and query["filters"] == "continent==150"
    assert query["sort"] == "-views" and query["maxResults"] == "10"
    assert query["currency"] == "EUR"


@pytest.mark.parametrize(
    ("given", "message"),
    [
        # Two time dimensions: "the request must use either 0 or 1".
        ({"metrics": ["views"], "dimensions": ["day", "month"]}, "No report"),
        # A metric no table has.
        ({"metrics": ["viewz"]}, "has the metrics viewz"),
        # The city report needs max_results of at most 250 and a sort.
        ({"metrics": ["views"], "dimensions": ["city"]}, "max_results of at most 250"),
        # liveOrOnDemand and averageViewPercentage are in no table together.
        (
            {"metrics": ["averageViewPercentage"], "dimensions": ["liveOrOnDemand"]},
            "No report",
        ),
        # Province needs the filter country==US, not another country.
        (
            {"metrics": ["views"], "dimensions": ["province"], "filters": "country==FR"},
            "No report",
        ),
        ({"metrics": ["views"], "filters": "country"}, "name==value"),
        ({"metrics": ["views"], "filters": "country==US;country==FR"}, "twice"),
        ({"metrics": ["views", "views"]}, "twice"),
        ({"metrics": ["views"], "sort": "views desc"}, "sort must be"),
        ({"metrics": ["views"], "dimensions": ["day;drop"]}, "must be names"),
        ({"metrics": []}, "metrics is required"),
        ({"metrics": ["views"], "currency": "eur"}, "three-letter"),
        ({"metrics": ["views"], "output": "csv"}, "output must be"),
    ],
)
def test_a_combination_youtube_does_not_support_is_refused_before_sending(
    given: dict[str, Any], message: str
) -> None:
    fake = FakeYouTube()
    result = run("get_channel_report", {**PERIOD, **given}, fake)
    assert result["error_code"] == "invalid_payload", result
    assert message in result["error"]
    assert result["definitely_no_external_effect"] is True
    assert fake.calls == []


def test_the_city_report_with_its_size_and_sort_is_sent() -> None:
    fake = FakeYouTube(table("city", "views"))
    given = {
        **PERIOD,
        "metrics": ["views"],
        "dimensions": ["city"],
        "sort": "-views",
        "max_results": 25,
    }
    result = run("get_channel_report", given, fake)
    assert result["ok"] is True, result
    assert result["result"]["matched_reports"] == ["User activity by city (<= 250 results)"]


def test_the_province_report_with_country_us_is_sent() -> None:
    fake = FakeYouTube(table("province", "views"))
    given = {**PERIOD, "metrics": ["views"], "dimensions": ["province"], "filters": "country==US"}
    assert run("get_channel_report", given, fake)["ok"] is True


def test_several_videos_in_the_filter_make_video_a_dimension() -> None:
    # "If you do specify multiple values for one of these filters, you can also add that
    # filter to the list of dimensions".
    fake = FakeYouTube(table("video", "views"))
    given = {**PERIOD, "metrics": ["views"], "dimensions": ["video"], "filters": "video==a,b"}
    result = run("get_channel_report", given, fake)
    assert result["ok"] is True, result
    assert query_of(fake)["filters"] == "video==a,b"
    one = run(
        "get_channel_report",
        {**PERIOD, "metrics": ["views"], "dimensions": ["video", "day"], "filters": "video==a"},
        FakeYouTube(),
    )
    assert one["error_code"] == "invalid_payload"


def test_revenue_metrics_need_the_revenue_connection_type() -> None:
    given = {**PERIOD, "metrics": ["views", "estimatedRevenue"], "dimensions": ["day"]}
    fake = FakeYouTube()
    result = run("get_channel_report", given, fake)
    assert result["error_code"] == "invalid_payload"
    assert "estimatedRevenue" in result["error"] and "with revenue" in result["error"]
    assert fake.calls == []
    fake = FakeYouTube(table("day", "views", "estimatedRevenue"))
    assert run("get_channel_report", given, fake, connection_type=MONETARY)["ok"] is True


def test_ad_performance_reports_need_the_revenue_connection_type() -> None:
    given = {**PERIOD, "metrics": ["adImpressions"], "dimensions": ["adType"]}
    result = run("get_channel_report", given, FakeYouTube())
    # adImpressions is also marked * (monetary) in the other tables.
    assert result["error_code"] == "invalid_payload" and "with revenue" in result["error"]
    fake = FakeYouTube(table("adType", "adImpressions"))
    result = run("get_channel_report", given, fake, connection_type=MONETARY)
    assert result["ok"] is True, result
    assert result["result"]["matched_reports"] == ["Ad performance by ad type"]


def test_a_channel_report_can_go_to_a_file() -> None:
    artifacts = Artifacts()
    fake = FakeYouTube(table("day", "views", rows=[["2026-01-01", 4]]))
    given = {**PERIOD, "metrics": ["views"], "dimensions": ["day"], "output": "file"}
    out = run("get_channel_report", given, fake, artifacts=artifacts)["result"]
    assert out["file"] == "artifact-1" and out["rows"] == [] and out["row_count"] == 1
    saved = artifacts.saved[0]
    assert saved["binding_key"] == "youtube_analytics_file"
    assert saved["content_type"] == "application/json"
    assert json.loads(saved["data"]) == {
        "column_headers": [{"name": "day"}, {"name": "views"}],
        "rows": [["2026-01-01", 4]],
    }


def test_analytics_errors_in_the_answer_fail_the_step() -> None:
    fake = FakeYouTube(ok({"errors": {"error": [{"reason": "badRequest"}]}}))
    result = run("get_channel_report", {**PERIOD, "metrics": ["views"]}, fake)
    assert result["error_code"] == "upstream_failure" and "badRequest" in result["error"]


def test_a_report_answer_that_is_not_a_table_is_invalid() -> None:
    fake = FakeYouTube(ok({"columnHeaders": [], "rows": ["x"]}))
    result = run("get_channel_report", {**PERIOD, "metrics": ["views"]}, fake)
    assert result["error_code"] == "invalid_response"


@pytest.mark.parametrize(
    "dates",
    [
        {"start_date": "2026-02-30", "end_date": "2026-03-01"},
        {"start_date": "2026-03-02", "end_date": "2026-03-01"},
        {"start_date": "2026/03/01", "end_date": "2026-03-01"},
    ],
)
def test_report_dates_are_checked(dates: dict[str, str]) -> None:
    fake = FakeYouTube()
    result = run("get_channel_report", {**dates, "metrics": ["views"]}, fake)
    assert result["error_code"] == "invalid_payload" and fake.calls == []


# -- video report and top videos ---------------------------------------------------------------


def test_a_video_report_filters_on_the_video() -> None:
    fake = FakeYouTube(table("country", "views"))
    given = {
        **PERIOD,
        "video_id": "V1",
        "metrics": ["views"],
        "dimensions": ["country"],
        "filters": "continent==150",
    }
    result = run("get_video_report", given, fake)
    assert result["ok"] is True, result
    assert query_of(fake)["filters"] == "video==V1;continent==150"


@pytest.mark.parametrize(
    ("given", "message"),
    [
        ({"metrics": ["views"]}, "video_id"),
        ({"video_id": "V 1", "metrics": ["views"]}, "YouTube ID"),
        ({"video_id": "V1", "metrics": ["views"], "filters": "video==V2"}, "may not name"),
        ({"video_id": "V1", "metrics": ["playlistStarts"]}, "No report"),
    ],
)
def test_video_report_inputs_are_checked(given: dict[str, Any], message: str) -> None:
    fake = FakeYouTube()
    result = run("get_video_report", {**PERIOD, **given}, fake)
    assert result["error_code"] == "invalid_payload", result
    assert message in result["error"] and fake.calls == []


def test_audience_retention_of_a_video() -> None:
    fake = FakeYouTube(table("elapsedVideoTimeRatio", "audienceWatchRatio"))
    given = {
        **PERIOD,
        "video_id": "V1",
        "metrics": ["audienceWatchRatio"],
        "dimensions": ["elapsedVideoTimeRatio"],
    }
    result = run("get_video_report", given, fake)
    assert result["ok"] is True, result
    assert result["result"]["matched_reports"] == ["Audience retention"]


def test_top_videos_by_default() -> None:
    fake = FakeYouTube(table("video", *composites.TOP_VIDEO_METRICS, rows=[["v1", 9, 1, 2, 3, 4]]))
    result = run("get_top_videos", PERIOD, fake)
    assert result["ok"] is True, result
    query = query_of(fake)
    assert query["dimensions"] == "video" and query["sort"] == "-views"
    assert query["maxResults"] == "10"
    assert query["metrics"] == ",".join(composites.TOP_VIDEO_METRICS)
    assert (
        "Top videos with optional regional filters (<= 200 results)"
        in (result["result"]["matched_reports"])
    )


def test_top_videos_for_a_country_by_watch_time() -> None:
    fake = FakeYouTube(table("video", "estimatedMinutesWatched"))
    given = {
        **PERIOD,
        "metrics": ["estimatedMinutesWatched"],
        "sort": "-estimatedMinutesWatched",
        "max_results": 200,
        "filters": "country==LT",
    }
    assert run("get_top_videos", given, fake)["ok"] is True
    assert query_of(fake)["filters"] == "country==LT"


@pytest.mark.parametrize(
    ("given", "message"),
    [
        ({"max_results": 201}, "from 1 to 200"),
        ({"sort": "-likes"}, "sort must be one of"),
        ({"filters": "video==a"}, "may not name"),
        ({"metrics": ["playlistStarts"]}, "No report"),
    ],
)
def test_top_video_inputs_are_checked(given: dict[str, Any], message: str) -> None:
    fake = FakeYouTube()
    result = run("get_top_videos", {**PERIOD, **given}, fake)
    assert result["error_code"] == "invalid_payload", result
    assert message in result["error"] and fake.calls == []


def test_top_videos_by_revenue_need_the_revenue_connection_type() -> None:
    given = {**PERIOD, "metrics": ["estimatedRevenue"], "sort": "-estimatedRevenue"}
    result = run("get_top_videos", given, FakeYouTube())
    assert result["error_code"] == "invalid_payload" and "with revenue" in result["error"]
    fake = FakeYouTube(table("video", "estimatedRevenue"))
    assert run("get_top_videos", given, fake, connection_type=MONETARY)["ok"] is True


# -- groups ----------------------------------------------------------------------------------


def test_all_my_groups() -> None:
    fake = FakeYouTube(
        ok({"items": [{"id": "g1"}], "nextPageToken": "T2"}),
        ok({"items": [{"id": "g2"}]}),
    )
    out = run("list_groups", {}, fake)["result"]
    assert [g["id"] for g in out["groups"]] == ["g1", "g2"]
    assert out["complete"] is True and out["next_page_token"] is None
    assert query_of(fake) == {"mine": "true"}
    assert query_of(fake, 1) == {"mine": "true", "pageToken": "T2"}


def test_groups_stop_at_max_groups_with_where_to_continue() -> None:
    fake = FakeYouTube(ok({"items": [{"id": "a"}, {"id": "b"}], "nextPageToken": "T2"}))
    out = run("list_groups", {"max_groups": 2, "page_token": "T1"}, fake)["result"]
    assert out["count"] == 2 and out["complete"] is False and out["next_page_token"] == "T2"
    assert query_of(fake)["pageToken"] == "T1"


def test_create_group_of_videos_by_default() -> None:
    fake = FakeYouTube(ok({"id": "G1", "snippet": {"title": "Launch"}}))
    out = run("create_group", {"title": "Launch"}, fake)
    assert out["ok"] is True, out
    assert out["external_effect_status"] == "succeeded"
    assert out["result"]["group_id"] == "G1" and out["result"]["applied"] is True
    assert fake.calls[0].body == {
        "snippet": {"title": "Launch"},
        "contentDetails": {"itemType": "youtube#video"},
    }
    assert fake.calls[0].key == "POST /v2/groups"


def test_create_group_of_playlists_and_unknown_item_types() -> None:
    fake = FakeYouTube(ok({"id": "G2"}))
    run("create_group", {"title": "P", "item_type": "youtube#playlist"}, fake)
    assert fake.calls[0].body["contentDetails"] == {"itemType": "youtube#playlist"}
    result = run("create_group", {"title": "P", "item_type": "youtube#song"}, FakeYouTube())
    assert result["error_code"] == "invalid_payload"


def test_add_video_to_group() -> None:
    fake = FakeYouTube(ok({"id": "GI1", "groupId": "G1"}))
    out = run("add_video_to_group", {"group_id": "G1", "video_id": "V1"}, fake)
    assert out["ok"] is True, out
    assert out["result"]["group_item_id"] == "GI1"
    assert out["result"]["already_in_group"] is False
    assert fake.calls[0].body == {
        "groupId": "G1",
        "resource": {"kind": "youtube#video", "id": "V1"},
    }
    assert fake.calls[0].key == "POST /v2/groupItems"


def test_a_video_already_in_the_group_is_answered_204() -> None:
    fake = FakeYouTube(raw(204, b""))
    out = run("add_video_to_group", {"group_id": "G1", "video_id": "V1"}, fake)
    assert out["ok"] is True, out
    assert out["external_effect_status"] == "succeeded"
    result = out["result"]
    assert result["already_in_group"] is True and result["group_item_id"] is None
    assert result["processing"] == "completed" and result["applied"] is True


def test_an_added_item_whose_answer_names_no_id_is_unknown() -> None:
    fake = FakeYouTube(ok({"groupId": "G1"}))
    out = run("add_video_to_group", {"group_id": "G1", "video_id": "V1"}, fake)
    assert out["external_effect_status"] == "timeout_unknown"
    assert "group item was created" in out["error"]


@pytest.mark.parametrize("operation_id", sorted(composites.COMPOSITE_WRITES))
def test_a_test_run_of_an_everyday_write_sends_nothing(operation_id: str) -> None:
    given = {
        "create_group": {"title": "t"},
        "add_video_to_group": {"group_id": "G1", "video_id": "V1"},
    }[operation_id]
    fake = FakeYouTube()
    result = run(operation_id, given, fake, test_mode=True)
    assert result["ok"] is True, result
    assert fake.calls == []
    assert result["definitely_no_external_effect"] is True
    assert result["result"]["processing"] is None and result["result"]["applied"] is False
