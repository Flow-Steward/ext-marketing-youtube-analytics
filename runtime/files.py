"""Workflow files: a report a step saves as a JSON workflow file.

The file is written with the SDK's ``write_artifact_stream`` under the binding that
contracts/artifact_policies.yaml declares; it is at most ``MAX_DOWNLOAD_BYTES``.
"""

from __future__ import annotations

from collections.abc import Mapping

from . import errors
from .context import Context
from .errors import ExtensionError

ARTIFACT_TIMEOUT_SECONDS = 120.0
MAX_DOWNLOAD_BYTES = 40 * errors.MIB

#: Must match contracts/artifact_policies.yaml (tests/reference/build_contracts.py).
DOWNLOAD_BINDING = "youtube_analytics_file"


def save(context: Context, data: bytes, *, content_type: str, what: str) -> str:
    """Save ``data`` as a workflow file; its handle."""
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise errors.no_effect(
            errors.RESPONSE_TOO_LARGE,
            f"{what} is larger than {errors.size_text(MAX_DOWNLOAD_BYTES)}",
        )
    try:
        written = context.artifact_writer(
            dict(context.payload),
            [data],
            binding_key=DOWNLOAD_BINDING,
            content_type=content_type,
            timeout_seconds=ARTIFACT_TIMEOUT_SECONDS,
        )
    except ExtensionError:
        raise
    except Exception:
        raise errors.no_effect(
            errors.ARTIFACT_OUTPUT_UNAVAILABLE, f"{what} could not be saved"
        ) from None
    handle = written.get("artifact_handle") if isinstance(written, Mapping) else None
    if not isinstance(handle, str) or not handle.strip():
        raise errors.no_effect(errors.ARTIFACT_OUTPUT_UNAVAILABLE, f"{what} could not be saved")
    return handle.strip()


__all__ = ["ARTIFACT_TIMEOUT_SECONDS", "DOWNLOAD_BINDING", "MAX_DOWNLOAD_BYTES", "save"]
