"""Runners of the generated steps: one method of the pinned Discovery documents each.

What each step accepts and how its answer is read comes from runtime/registry.json,
built from the pinned documents by tests/reference/build_contracts.py:

- the path parameter is required text, percent-encoded as one path segment;
- query parameters are typed by the document (text, whole number with its minimum and
  maximum, true/false, RFC 3339 date-time, YYYY-MM-DD date, allowed values); a
  ``repeated`` one takes a list and sends one parameter per value;
- a request body (the method's ``request`` schema) is the ``body`` input, sent as given
  with exact decimals; a field the schema does not list is refused before sending,
  because Google refuses unknown fields;
- a list method (``pageToken`` in, ``nextPageToken`` and ``items`` out) returns ``items``,
  ``count``, ``complete`` and ``next_page_token``; with ``all_pages`` it reads page after
  page (runtime/pages.py);
- a JSON answer is ``data``; one nested deeper than 48 levels is not read (a read fails
  with ``invalid_response``, a confirmed write returns its facts with ``data`` empty and
  a warning);
- a write returns ``processing``: ``completed`` when YouTube answered that the change is
  made (no method of the YouTube Analytics API is processed afterwards).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import quote

from . import budget, errors, nesting, outcome, pages
from .context import Context
from .errors import invalid
from .params import check, integer, wire
from .transport import MAX_ANSWER_BYTES, Answer, Call, TooDeep, dumps_json

REGISTRY_FILE = Path(__file__).resolve().parent / "registry.json"
#: Inputs a paged step adds.
PAGE_INPUTS = frozenset({"all_pages", "max_items"})
#: The most records ``all_pages`` reads in one step.
MAX_ITEMS = 100_000
DEFAULT_ITEMS = 10_000


@cache
def _data() -> dict[str, Any]:
    return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))


def registry() -> dict[str, dict[str, Any]]:
    return dict(_data()["operations"])


def spec(operation_id: str) -> dict[str, Any]:
    return _data()["operations"][operation_id]


def channel_reports() -> list[dict[str, Any]]:
    """The report tables of YouTube's channel reports page (runtime/reports.py)."""
    return list(_data()["channel_reports"])


def inputs_of(entry: Mapping[str, Any]) -> set[str]:
    names = {p["input"] for p in entry["path_params"] + entry["query"]}
    body = entry["body"]
    if body:
        names.add("body")
    if entry["pager"]:
        names |= PAGE_INPUTS
    return names


@dataclass
class Plan:
    """A checked request."""

    method: str
    path: str
    api: str
    shown: str
    query: list[tuple[str, str]] = field(default_factory=list)
    body: bytes | None = None
    content_type: str | None = None
    all_pages: bool = False
    max_items: int = DEFAULT_ITEMS


def prepare(operation_id: str, operation_input: Mapping[str, Any]) -> Plan:
    """The checked request of a generated step (also its test-run check)."""
    entry = spec(operation_id)
    given = {k: v for k, v in operation_input.items() if k != "connection_ref"}
    unknown = sorted(set(given) - inputs_of(entry))
    if unknown:
        raise invalid(f"The step input has unknown fields: {', '.join(unknown[:10])}")
    path = entry["path"]
    for prm in entry["path_params"]:
        value = given.get(prm["input"])
        if value is None or value == "":
            raise invalid(f"{prm['input']} is required")
        segment = check(prm["node"], value, prm["input"])
        path = path.replace("{" + prm["name"] + "}", quote(str(segment), safe=""))
    plan = Plan(
        method=entry["method"],
        path=path,
        api=entry["api"],
        shown=f"{entry['method']} {entry['path']}",
    )
    for prm in entry["query"]:
        value = given.get(prm["input"])
        if value is None or value == "" or value == []:
            if prm["node"]["required"]:
                raise invalid(f"{prm['input']} is required")
            continue
        checked = check(prm["node"], value, prm["input"])
        if isinstance(checked, list):
            plan.query += [(prm["name"], wire(item)) for item in checked]
        else:
            plan.query.append((prm["name"], wire(checked)))
    if entry["pager"]:
        flag = given.get("all_pages", False)
        if not isinstance(flag, bool):
            raise invalid("all_pages must be true or false")
        plan.all_pages = flag
        if "max_items" in given:
            if not flag:
                raise invalid("max_items applies only with all_pages")
            plan.max_items = integer(
                {"minimum": 1, "maximum": MAX_ITEMS}, given["max_items"], "max_items"
            )
    _body(entry, given, plan)
    return plan


def _body(entry: Mapping[str, Any], given: Mapping[str, Any], plan: Plan) -> None:
    body = entry["body"]
    if not body:
        return
    shape = body["json"]
    value = given.get("body")
    if value in (None, "", {}, []):
        raise invalid(f"body is required: the {shape['schema']} resource as JSON")
    if not isinstance(value, Mapping):
        raise invalid("body must be a JSON object")
    extra = sorted(str(k) for k in value if k not in shape["properties"])
    if extra:
        raise invalid(
            f"body has fields the {shape['schema']} resource does not have: "
            + ", ".join(extra[:10])
        )
    plan.body = dumps_json(value).encode("utf-8")
    plan.content_type = "application/json"


def to_call(entry: Mapping[str, Any], plan: Plan) -> Call:
    return Call(
        method=plan.method,
        path=plan.path,
        shown=plan.shown,
        api=plan.api,
        query=tuple(plan.query),
        body=plan.body,
        content_type=plan.content_type,
        limit=MAX_ANSWER_BYTES,
    )


def _read_json(context: Context, answer: Answer, shown: str) -> Any:
    """A read's JSON value; an empty or invalid answer is an error (nothing changed)."""
    if answer.empty:
        raise errors.no_effect(
            errors.INVALID_RESPONSE,
            f"YouTube answered {shown} without a body",
            failure_class="provider",
            retryable=False,
        )
    try:
        return context.transport.json(answer)
    except ValueError as exc:
        what = (
            f"JSON nested deeper than {nesting.MAX_ANSWER_DEPTH} levels; it is not read"
            if isinstance(exc, TooDeep)
            else "something that is not JSON"
        )
        raise errors.no_effect(
            errors.INVALID_RESPONSE,
            f"YouTube answered {shown} with {what}",
            failure_class="provider",
            retryable=False,
        ) from None


def refuse_failed_report(context: Context, data: Any, shown: str) -> None:
    """A report answer whose ``errors`` is set failed, whatever its HTTP status: the
    Discovery document says of QueryResponse.errors "When set, indicates that the
    operation failed." A read changed nothing."""
    failed = data.get("errors") if isinstance(data, Mapping) else None
    if failed:
        detail = errors.safe_text(dumps_json(context.transport.scrub(failed)), 400)
        raise errors.no_effect(
            errors.UPSTREAM_FAILURE,
            f"YouTube Analytics answered {shown} with errors: {detail}",
            failure_class="provider",
            retryable=False,
        )


def read_result(
    context: Context, entry: Mapping[str, Any], answer: Answer, plan: Plan
) -> dict[str, Any]:
    """The outputs of a read YouTube answered with a success status."""
    result: dict[str, Any] = {"status": answer.status}
    data = _read_json(context, answer, plan.shown)
    if entry.get("fails_with_errors"):
        refuse_failed_report(context, data, plan.shown)
    if entry["pager"]:
        result.update(pages.one_page(data, plan.shown))
    else:
        result["data"] = data
    result["etag"] = answer.headers.get("ETag")
    result["warnings"] = []
    return result


def write_result(
    context: Context, entry: Mapping[str, Any], answer: Answer, plan: Plan
) -> dict[str, Any]:
    """The outputs of a write YouTube answered with a success status (table T)."""
    out = outcome.write_outcome(
        context,
        answer,
        plan.shown,
        entry=entry,
        promised=entry["answer"] == "json",
    )
    result: dict[str, Any] = {"status": answer.status, **out}
    result["etag"] = answer.headers.get("ETag")
    result["warnings"] = out["warnings"]
    return result


def run(context: Context, operation_id: str) -> dict[str, Any]:
    entry = spec(operation_id)
    plan = prepare(operation_id, context.operation_input)
    if entry["kind"] == "read":
        if plan.all_pages:
            return pages.read_all(context, operation_id, plan)
        answer = context.transport.read(to_call(entry, plan))
        result = read_result(context, entry, answer, plan)
        budget.ensure_fits(result)
        return result
    answer = context.transport.write(to_call(entry, plan))
    return write_result(context, entry, answer, plan)


__all__ = [
    "Plan",
    "channel_reports",
    "inputs_of",
    "prepare",
    "read_result",
    "registry",
    "run",
    "spec",
    "to_call",
    "write_result",
]
