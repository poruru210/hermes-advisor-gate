"""Observer hook handlers for Advisor Gate."""

from __future__ import annotations

import json
from typing import Any

from advisor_gate.store import ReceiptStore, redact_secrets, utc_now_iso
from advisor_gate.tool_schemas import ADVISOR_TOOL_NAMES


def _result_text_has_error(result: str) -> bool:
    text = result.strip()
    if not text:
        return False
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        error_value = parsed.get("error")
        if error_value:
            return True
    lowered = text[:800].lower()
    return (
        lowered.startswith("error:")
        or lowered.startswith("error executing tool")
        or "traceback (most recent call last)" in lowered
    )


def _post_tool_call_requires_exception(kwargs: dict[str, Any], result: str) -> bool:
    tool_name = str(kwargs.get("tool_name") or "").strip()
    if tool_name in ADVISOR_TOOL_NAMES:
        return False
    status = str(kwargs.get("status") or "").strip().lower()
    error_type = str(kwargs.get("error_type") or "").strip().lower()
    if error_type in {"plugin_block", "tool_scope_block", "approval_denied"}:
        return False
    if status in {"error", "failed", "exception"}:
        return True
    if error_type:
        return True
    return _result_text_has_error(result)


def on_subagent_start(store: ReceiptStore, **kwargs: Any) -> None:
    store.append(
        {
            "timestamp": utc_now_iso(),
            "source": "subagent_start",
            "session_id": kwargs.get("parent_session_id") or "",
            "phase": "A2_DELEGATION",
            "event": "subagent_start",
            "extra": redact_secrets(kwargs),
        }
    )


def on_subagent_stop(store: ReceiptStore, **kwargs: Any) -> None:
    store.append(
        {
            "timestamp": utc_now_iso(),
            "source": "subagent_stop",
            "session_id": kwargs.get("parent_session_id") or "",
            "phase": "A2_DELEGATION",
            "event": "subagent_stop",
            "extra": redact_secrets(kwargs),
        }
    )


def on_post_tool_call(store: ReceiptStore, **kwargs: Any) -> None:
    result = str(kwargs.get("result") or "")
    requires_a3_exception = _post_tool_call_requires_exception(kwargs, result)
    store.append(
        {
            "timestamp": utc_now_iso(),
            "source": "post_tool_call",
            "session_id": kwargs.get("session_id") or kwargs.get("task_id") or "",
            "phase": "A3_EXCEPTION",
            "event": "post_tool_call",
            "extra": redact_secrets(
                {
                    "tool_name": kwargs.get("tool_name"),
                    "args": kwargs.get("args") or kwargs.get("arguments"),
                    "duration_ms": kwargs.get("duration_ms"),
                    "status": kwargs.get("status"),
                    "error_type": kwargs.get("error_type"),
                    "error_message": kwargs.get("error_message"),
                    "requires_a3_exception": requires_a3_exception,
                    "result_preview": result[:2000],
                    "truncated": len(result) > 2000,
                }
            ),
        }
    )
