"""The generated contracts match their sources; every method of the source is a step or an
exclusion with its reason; forms, inputs and the runtime agree; the extension's standing
rules (ids, names, outputs, OAuth, UI, icon, version) hold."""

from __future__ import annotations

import collections
import hashlib
import json
import re
import struct
import sys
from typing import Any

import pytest
import yaml
from support import BUNDLE

sys.path.insert(0, str(BUNDLE / "tests" / "reference"))

import build_contracts  # noqa: E402
import composite_specs  # noqa: E402
import names  # noqa: E402

from runtime import catalog, composites, files, generic, limits, reports  # noqa: E402

OUTPUTS = build_contracts.outputs()
EVERYDAY = [c["operation_id"] for c in composite_specs.COMPOSITES]
REPOSITORY = "https://github.com/Flow-Steward/ext-marketing-youtube-analytics"
SCOPE = "https://www.googleapis.com/auth/"


def load(path: str) -> Any:
    return yaml.safe_load((BUNDLE / path).read_text(encoding="utf-8"))


def operations() -> list[dict[str, Any]]:
    return load("contracts/operation_manifest.yaml")["operations"]


def source_methods() -> dict[str, dict[str, Any]]:
    return {m["id"]: m for _, m in build_contracts.all_methods()}


@pytest.mark.parametrize("path", sorted(OUTPUTS))
def test_generated_files_are_current(path: str) -> None:
    assert (BUNDLE / path).read_text(encoding="utf-8") == build_contracts.render(
        path, OUTPUTS[path]
    ), f"{path} drifted: run python3 tests/reference/build_contracts.py"


def test_every_method_of_the_source_is_a_step_or_excluded_with_a_reason() -> None:
    methods = source_methods()
    assert len(build_contracts.methods()) == 8
    registry = generic.registry()
    covered = {e["vendor_method_id"] for e in registry.values()}
    excluded = set(names.EXCLUDED)
    assert covered | excluded == set(methods)
    assert not covered & excluded
    assert excluded == set()
    assert registry_counts(registry) == {"GET": 3, "POST": 2, "PUT": 1, "DELETE": 2}
    assert len(registry) == 8
    manifest = [o["operation_id"] for o in operations()]
    assert manifest[: len(EVERYDAY)] == EVERYDAY
    assert sorted(manifest[len(EVERYDAY) :]) == sorted(registry) and len(manifest) == 15
    assert set(manifest) | {"verify_identity"} == set(catalog.OPERATION_IDS)
    assert set(names.TITLES) == covered


def registry_counts(registry: dict[str, Any]) -> dict[str, int]:
    return dict(collections.Counter(e["method"] for e in registry.values()))


def test_the_coverage_page_names_what_is_not_in_this_extension() -> None:
    body = load("ui/pages/api-coverage.yaml")["components"][0]["body"]
    assert "YouTube Reporting API" in body and "YouTube Data API v3" in body
    assert "flowsteward.youtube" in body


def test_step_ids_are_frozen_unique_and_never_vendor_ids() -> None:
    ids = json.loads((BUNDLE / "tests/reference/step_ids.json").read_text())
    assert set(ids) == set(source_methods()) - set(names.EXCLUDED)
    values = list(ids.values()) + EVERYDAY
    assert len(values) == len(set(values))
    assert all(re.fullmatch(r"[a-z][a-z0-9_]{2,80}", v) for v in values)
    assert set(generic.registry()) == set(ids.values())
    assert not set(source_methods()) & set(values)


def test_titles_are_verb_first_and_unique() -> None:
    titles = [o["display_name"] for o in operations()]
    assert len(titles) == len(set(titles))
    for title in titles:
        assert title.split()[0] in names.VERBS, title


def test_everyday_steps_come_first_and_reads_precede_deletes_within_a_resource() -> None:
    ids = [o["operation_id"] for o in operations()]
    assert ids[: len(EVERYDAY)] == EVERYDAY
    registry = generic.registry()
    by_resource: dict[str, list[str]] = collections.defaultdict(list)
    for oid in ids[len(EVERYDAY) :]:
        by_resource[registry[oid]["resource"]].append(registry[oid]["method"])
    for resource, methods in by_resource.items():
        if "GET" in methods:
            assert methods[0] == "GET", resource
        if "DELETE" in methods:
            assert methods[-1] == "DELETE", resource


def test_every_step_has_warnings_and_every_write_is_a_suppressed_effect() -> None:
    effects = load("extension.yaml")["external_effects"]
    effect_ids = {e["operation_id"] for e in effects}
    for op in operations():
        names_out = [o["name"] for o in op["outputs"]]
        assert "warnings" in names_out, op["operation_id"]
        write = op["operation_kind"] == "action"
        assert write == (op["operation_id"] in effect_ids)
        assert write == (op["operation_id"] in catalog.EFFECT_OPERATION_IDS)
        if write:
            assert {
                "external_effect_status",
                "definitely_no_external_effect",
                "processing",
                "applied",
                "check",
            } <= set(names_out)
            assert "timeout_unknown" in op["error_codes"]
    generated_writes = {k for k, v in generic.registry().items() if v["kind"] == "write"}
    assert generated_writes | composites.COMPOSITE_WRITES == effect_ids
    assert len(effect_ids) == 5 + 2
    assert all(
        e["idempotency"] == "required" and e["test_mode_behavior"] == "suppress" for e in effects
    )


def test_reads_are_exactly_the_get_methods() -> None:
    for oid, entry in generic.registry().items():
        assert (entry["kind"] == "read") == (entry["method"] == "GET"), oid


def test_forms_inputs_and_runtime_agree() -> None:
    forms = {f["operation_id"]: f for f in load("contracts/step_ui_manifest.yaml")["forms"]}
    actions = {a["action_id"]: a for a in load("ui/actions/actions.yaml")["actions"]}
    registry = generic.registry()
    for op in operations():
        oid = op["operation_id"]
        inputs = [i["name"] for i in op["inputs"] if i["name"] != "connection_ref"]
        assert [f["name"] for f in forms[oid]["fields"]] == inputs, oid
        assert [p["name"] for p in actions[oid]["parameters"]] == ["connection_ref", *inputs]
        if oid in registry:
            assert set(inputs) == generic.inputs_of(registry[oid]), oid
        for item in op["inputs"]:
            if item["value_type"] == "artifact_handle":
                field = next(f for f in forms[oid]["fields"] if f["name"] == item["name"])
                assert field["widget_type"] == "artifact_picker"


def test_every_everyday_step_refuses_inputs_it_does_not_declare() -> None:
    from support import FakeYouTube, run

    for spec in composite_specs.COMPOSITES:
        fake = FakeYouTube()
        result = run(spec["operation_id"], {"surely_unknown": 1}, fake, test_mode=True)
        assert result["error_code"] == "invalid_payload", spec["operation_id"]
        assert "surely_unknown" in result["error"] and fake.calls == []


def test_the_post_connect_action_is_the_only_action_that_is_not_a_step() -> None:
    # verify_identity reads channels.list of the YouTube Data API (mine), allowed by the
    # youtube.readonly scope every connection type asks for.
    actions = {a["action_id"] for a in load("ui/actions/actions.yaml")["actions"]}
    assert actions == {o["operation_id"] for o in operations()} | {"verify_identity"}
    assert "verify_identity" in catalog.OPERATION_IDS


def test_oauth_is_declared_like_the_flow_steward_youtube_extension() -> None:
    providers = load("extension.yaml")["runtime"]["extension_contract_v2"]["oauth_providers"]
    assert [p["provider_id"] for p in providers] == ["google_youtube"]
    provider = providers[0]
    assert provider["flow"] == {"type": "authorization_code", "pkce": "s256"}
    assert provider["authorization_endpoint"] == {
        "url": "https://accounts.google.com/o/oauth2/v2/auth"
    }
    assert provider["token_endpoint"] == {
        "url": "https://oauth2.googleapis.com/token",
        "client_auth_method": "client_secret_post",
    }
    assert provider["revocation_endpoint"] == {"url": "https://oauth2.googleapis.com/revoke"}
    assert provider["callback_id"] == "oauth_authorization"
    assert provider["post_connect_action_id"] == "verify_identity"
    intent = provider["authorization_intents"][0]
    assert intent["static_parameters"] == {
        "access_type": "offline",
        "include_granted_scopes": False,
        "prompt": "consent select_account",
    }
    fields = {f["field_id"]: f for f in provider["credential_fields"]}
    assert set(fields) == {"client_id", "client_secret"}
    assert fields["client_secret"]["secret"] is True and fields["client_id"]["secret"] is False
    callbacks = load("extension.yaml")["callbacks"]
    assert callbacks == [
        {
            "callback_id": "oauth_authorization",
            "purpose": "oauth_authorization",
            "methods": ["GET"],
            "connection_scoped": False,
        }
    ]


def test_connection_types_ask_for_scopes_the_source_names() -> None:
    types = load("contracts/connection_types.yaml")["connection_types"]
    assert [t["connection_type_id"] for t in types] == [
        "youtube_analytics_channel",
        "youtube_analytics_channel_monetary",
    ]
    known = set(build_contracts.document()["auth"]["oauth2"]["scopes"])
    for row in types:
        auth = row["auth"]
        assert auth["type"] == "oauth2" and auth["provider_id"] == "google_youtube"
        assert set(auth["scopes"]["required"]) <= known
        assert auth["scopes"]["optional"] == []
        assert row["capabilities"] == {"test_connection": True}
    assert types[0]["auth"]["scopes"]["required"] == [
        SCOPE + "yt-analytics.readonly",
        SCOPE + "youtube.readonly",
    ]
    assert types[1]["auth"]["scopes"]["required"] == [
        SCOPE + "yt-analytics.readonly",
        SCOPE + "yt-analytics-monetary.readonly",
        SCOPE + "youtube.readonly",
    ]
    assert generic._data()["revenue_connection_types"] == ["youtube_analytics_channel_monetary"]
    from runtime.connection import CONNECTION_TYPES, REVENUE_TYPES

    assert CONNECTION_TYPES == {t["connection_type_id"] for t in types}
    assert REVENUE_TYPES == {"youtube_analytics_channel_monetary"}


def test_the_analytics_scope_allows_every_method_groups_included() -> None:
    # The Discovery document names yt-analytics.readonly for every method, the group
    # methods included (groups.insert/update/delete, groupItems.insert/delete); the
    # reference pages of groups.insert and groupItems.insert list it too.
    for oid, entry in generic.registry().items():
        assert SCOPE + "yt-analytics.readonly" in entry["scopes"], oid
        assert SCOPE + "yt-analytics-monetary.readonly" in entry["scopes"], oid


def test_every_step_names_its_scopes() -> None:
    for oid, entry in generic.registry().items():
        for scope in entry["scopes"]:
            assert build_contracts.short_scope(scope) in entry["description"], oid


def test_report_files_are_declared() -> None:
    policies = {
        p["operation_id"]: p for p in load("contracts/artifact_policies.yaml")["artifact_policies"]
    }
    assert set(policies) == catalog.FILE_OUTPUT_IDS == {"get_channel_report", "get_video_report"}
    for oid in catalog.FILE_OUTPUT_IDS:
        assert policies[oid]["outputs"][0]["binding_key"] == files.DOWNLOAD_BINDING
        assert "inputs" not in policies[oid]


def test_no_write_is_processed_afterwards() -> None:
    for oid, entry in generic.registry().items():
        if entry["kind"] == "write":
            assert entry["processing"] == {"accepted_always": False, "check": None}, oid


def test_the_report_tables_are_the_extracted_ones() -> None:
    tables = build_contracts.channel_reports()
    kept = generic.channel_reports()
    assert len(kept) == len(tables["reports"]) == 47
    assert [r["id"] for r in kept] == [r["id"] for r in tables["reports"]]
    assert len({r["id"] for r in kept}) == 47
    by_id = {r["id"]: r for r in kept}
    top = by_id["Top videos with optional regional filters (<= 200 results)"]
    assert top["max_results"] == 200 and top["sort_required"] is True
    assert top["sort_options"] == composite_specs.TOP_VIDEO_SORTS == composites.TOP_VIDEO_SORTS
    assert composite_specs.TOP_VIDEO_METRICS == composites.TOP_VIDEO_METRICS
    metrics = {m for g in top["metrics"] for m in g["values"]}
    assert set(composites.TOP_VIDEO_METRICS) <= metrics
    assert composite_specs.ITEM_TYPES == composites.ITEM_TYPES
    assert by_id["Ad performance by ad type"]["monetary_scope_required"] is True
    assert "estimatedRevenue" in reports.monetary(kept)
    assert by_id["User activity by province"]["fixed_filters"] == {"country": "US"}
    assert by_id["User activity by city (<= 250 results)"]["max_results"] == 250


def test_item_types_are_the_ones_the_source_names() -> None:
    schema = build_contracts.document()["schemas"]["GroupContentDetails"]
    for item_type in composite_specs.ITEM_TYPES:
        assert item_type in schema["properties"]["itemType"]["description"]


def _pages() -> list[tuple[str, str]]:
    manifest = load("ui/ui_manifest.yaml")
    out = []
    for ref in manifest["pages"]:
        page = load("ui/" + ref["ref"])
        for comp in page.get("components", []):
            out.append((page["page_id"], str(comp.get("body") or comp.get("content") or "")))
    return out


def test_every_page_is_in_the_manifest() -> None:
    refs = {r["ref"] for r in load("ui/ui_manifest.yaml")["pages"]}
    on_disk = {f"pages/{p.name}" for p in (BUNDLE / "ui" / "pages").glob("*.yaml")}
    assert refs == on_disk


def test_ui_pages_have_no_tables_and_no_forbidden_words() -> None:
    for page_id, body in _pages():
        for line in body.splitlines():
            assert not line.strip().startswith("|"), (page_id, line)
        lowered = body.lower()
        for word in ("not verified", "unverified", "не проверено", "todo", "tbd"):
            assert word not in lowered, (page_id, word)


def test_the_icon_is_a_square_png_with_the_logo_at_least_100_px_tall() -> None:
    data = (BUNDLE / "icon.png").read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert struct.unpack(">II", data[16:24]) == (256, 256)
    assert "180 × 126" in (BUNDLE / "BRANDING.md").read_text(encoding="utf-8")
    branding = (BUNDLE / "BRANDING.md").read_text(encoding="utf-8")
    assert hashlib.sha256(data).hexdigest() in branding
    assert "youtube-icon.zip" in branding
    assert "ca9b5104387e0f7afcfda3a79c910449561112f1077177dd0d64f8c72f56e476" in branding


def test_version_step_limit_and_changelog() -> None:
    manifest = load("extension.yaml")
    assert manifest["version"] == "0.1.3" == build_contracts.VERSION
    assert manifest["entrypoint"]["timeout_seconds"] == 600
    assert limits.STEP_TIMEOUT_SECONDS == 600
    changelog = (BUNDLE / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.splitlines()[2].startswith("## 0.1.3")
    assert "0.1.3" in json.dumps(load("ui/pages/changelog.yaml"))


def test_vendor_listing_and_repository() -> None:
    manifest = load("extension.yaml")
    assert manifest["extension_id"] == "flowsteward.youtube-analytics"
    # Flow Steward installs the bundle in a folder named after the id ("." and "-" become
    # "_"); the checkout folder itself may have any name (the repository's, on GitHub).
    folder = manifest["extension_id"].replace(".", "_").replace("-", "_")
    assert folder == "flowsteward_youtube_analytics"
    assert manifest["vendor"] == {
        "name": "Flow Steward",
        "support_url": REPOSITORY + "/issues",
        "website_url": REPOSITORY,
    }
    assert manifest["listing"]["categories"] == ["marketing", "data"]
    assert manifest["listing"]["category"] == "marketing"
    support = json.dumps(load("ui/pages/support.yaml"))
    assert REPOSITORY in support
    readme = (BUNDLE / "README.md").read_text(encoding="utf-8")
    assert REPOSITORY in readme


def test_the_runtime_names_no_server_beyond_youtube_analytics() -> None:
    hosts = set()
    for path in (BUNDLE / "runtime").glob("*.py"):
        hosts |= set(re.findall(r"https://([a-z0-9.-]+)", path.read_text(encoding="utf-8")))
    assert hosts <= {"youtubeanalytics.googleapis.com", "developers.google.com"}
    egress = set(load("extension.yaml")["egress"]["hosts"])
    # www.googleapis.com only for verify_identity (YouTube Data API channels.list, mine).
    assert egress == {"youtubeanalytics.googleapis.com", "www.googleapis.com"}
    for api, facts in build_contracts.sources_facts().items():
        assert facts["root_url"].removeprefix("https://").rstrip("/") in egress, api


def test_composite_writes_and_validators_are_declared() -> None:
    assert set(composites.VALIDATORS) == composites.COMPOSITE_WRITES == set(composites.NEUTRAL)
    assert composites.COMPOSITE_WRITES == {
        s["operation_id"] for s in composite_specs.COMPOSITES if s["kind"] == "write"
    }


def test_readme_follows_the_structure() -> None:
    readme = (BUNDLE / "README.md").read_text(encoding="utf-8")
    assert readme.startswith("# YouTube Analytics integration for Flow Steward\n")
    headings = re.findall(r"^## (.+)$", readme, re.MULTILINE)
    assert headings == [
        "What is this",
        "What you can automate",
        "Why teams use it",
        "What's inside",
        "Get started",
        "Requirements",
        "FAQ",
        "In your language",
        "Links",
        "For developers",
    ]
    assert '<img src="icon.png"' in readme and "img.shields.io" in readme
    assert readme.rstrip().splitlines()[-1].startswith("YouTube and the YouTube logo")


def test_the_post_connect_action_names_the_channel_and_is_not_a_step() -> None:
    [action] = [
        a for a in load("ui/actions/actions.yaml")["actions"] if a["action_id"] == "verify_identity"
    ]
    assert action["workflow_visible"] is False and action["mutates_platform"] is False
    assert "verify_identity" not in {o["operation_id"] for o in operations()}
    provider = load("extension.yaml")["runtime"]["extension_contract_v2"]["oauth_providers"][0]
    assert provider["post_connect_action_id"] == "verify_identity"


def test_every_connection_type_asks_for_youtube_readonly_to_know_the_channel() -> None:
    readonly = "https://www.googleapis.com/auth/youtube.readonly"
    for row in load("contracts/connection_types.yaml")["connection_types"]:
        assert readonly in row["auth"]["scopes"]["required"], row["connection_type_id"]
    assert "www.googleapis.com" in load("extension.yaml")["egress"]["hosts"]
