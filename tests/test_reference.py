"""The pinned sources are the downloaded ones, and the report tables are extracted from the
pinned documentation page."""

from __future__ import annotations

import hashlib
import json
import sys

import pytest
from support import BUNDLE

sys.path.insert(0, str(BUNDLE / "tests" / "reference"))

import build_contracts  # noqa: E402
import extract_channel_reports  # noqa: E402


def test_the_discovery_document_is_the_pinned_one() -> None:
    pin = build_contracts.SOURCES["analytics"]
    raw = (BUNDLE / "tests" / "reference" / pin["file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == pin["sha256"]
    assert len(raw) == pin["bytes"] == 35631
    assert pin["downloaded"] == "2026-11-23"
    assert pin["url"] == "https://youtubeanalytics.googleapis.com/$discovery/rest?version=v2"


def test_the_pinned_document_is_what_it_says() -> None:
    facts = build_contracts.sources_facts()
    assert set(facts) == {"analytics"}
    assert facts["analytics"]["name"] == "youtubeAnalytics"
    assert facts["analytics"]["version"] == "v2"
    assert facts["analytics"]["revision"] == "20261122"
    assert facts["analytics"]["root_url"] == "https://youtubeanalytics.googleapis.com/"


def test_a_changed_document_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "youtubeAnalytics_v2.json").write_text("{}")
    monkeypatch.setattr(build_contracts, "HERE", tmp_path)
    with pytest.raises(SystemExit, match="not the pinned document"):
        build_contracts.document()


@pytest.mark.skipif(
    not extract_channel_reports.SOURCE.exists(), reason="the documentation page is not committed"
)
def test_the_report_tables_are_extracted_from_the_pinned_page() -> None:
    assert extract_channel_reports.extract(
        extract_channel_reports.SOURCE.read_bytes()
    ) == json.loads(extract_channel_reports.OUTPUT.read_text(encoding="utf-8"))


def test_a_changed_report_page_is_refused() -> None:
    with pytest.raises(SystemExit, match="the documentation page changed"):
        extract_channel_reports.extract(b"<html></html>")


def test_the_report_page_pin_is_the_downloaded_one() -> None:
    source = build_contracts.channel_reports()["source"]
    assert source["sha256"] == extract_channel_reports.SHA256
    assert source["bytes"] == extract_channel_reports.BYTES == 306166
    assert source["downloaded"] == "2026-11-23" and source["last_updated"] == "2026-11-12"
    assert source["url"] == "https://developers.google.com/youtube/analytics/channel_reports?hl=en"


def test_the_usage_terms_are_the_pages_own() -> None:
    usages = {
        g["usage"]
        for r in build_contracts.channel_reports()["reports"]
        for part in ("dimensions", "metrics", "filters")
        for g in r[part]
    }
    assert usages == set(extract_channel_reports.USAGE)
