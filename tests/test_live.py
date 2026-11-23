"""Read-only checks against the real YouTube Analytics API.

They run only when ``YOUTUBE_ANALYTICS_TOKEN_FILE`` names a file holding a current OAuth
access token of a test channel (the scope yt-analytics.readonly, the connection type
YouTube channel analytics); otherwise they are skipped. They only read: nothing is
changed on the channel and no group is created.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from support import payload

from runtime.operations import handle_runtime

TOKEN_FILE = os.environ.get("YOUTUBE_ANALYTICS_TOKEN_FILE", "")

pytestmark = pytest.mark.skipif(
    not TOKEN_FILE or not Path(TOKEN_FILE).is_file(),
    reason=(
        "set YOUTUBE_ANALYTICS_TOKEN_FILE to a file with a YouTube Analytics access token to "
        "run the live reads"
    ),
)


def live(operation_id: str, given: dict[str, Any] | None = None) -> dict[str, Any]:
    token = Path(TOKEN_FILE).read_text(encoding="utf-8").strip()
    response = handle_runtime(payload(operation_id, given or {}, token=token))
    assert token not in json.dumps(response, default=str)
    return response


def _period() -> dict[str, str]:
    end = date.today() - timedelta(days=2)
    return {"start_date": (end - timedelta(days=27)).isoformat(), "end_date": end.isoformat()}


def test_live_the_connection_reads_a_report() -> None:
    response = live("test_connection")
    assert response["ok"] is True, response
    assert response["result"]["connected"] is True


def test_live_a_channel_report_by_day() -> None:
    response = live(
        "get_channel_report",
        {**_period(), "metrics": ["views", "estimatedMinutesWatched"], "dimensions": ["day"]},
    )
    assert response["ok"] is True, response
    headers = [h["name"] for h in response["result"]["column_headers"]]
    assert headers == ["day", "views", "estimatedMinutesWatched"]


def test_live_top_videos_and_groups() -> None:
    top = live("get_top_videos", {**_period(), "max_results": 5})
    assert top["ok"] is True, top
    assert top["result"]["row_count"] <= 5
    groups = live("list_groups", {"max_groups": 10})
    assert groups["ok"] is True, groups
