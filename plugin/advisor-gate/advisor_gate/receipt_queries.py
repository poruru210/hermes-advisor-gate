"""Receipt lookup and freshness helpers for Advisor Gate."""

from __future__ import annotations

from typing import Any, cast

from advisor_gate.policy import is_gate_passed
from advisor_gate.schemas import (
    AdvisorPhase,
    AdvisorResult,
    ResolutionGate,
    resolution_gate_from_dict,
    result_from_dict,
)
from advisor_gate.store import ReceiptStore, redact_secrets
from advisor_gate.tool_schemas import ADVISOR_TOOL_NAMES


def latest_indexed_entry(
    store: ReceiptStore,
    *,
    session_id: str,
    phase: str,
) -> tuple[int, dict[str, Any]] | None:
    for index, entry in reversed(list(enumerate(store.read_all()))):
        if entry.get("session_id") == session_id and entry.get("phase") == phase:
            return index, entry
    return None


def entry_call_context(entry: dict[str, Any]) -> dict[str, Any]:
    extra = entry.get("extra")
    if not isinstance(extra, dict):
        return {}
    context = extra.get("call_context")
    return context if isinstance(context, dict) else {}


def entry_turn_id(entry: dict[str, Any]) -> str:
    return str(entry_call_context(entry).get("turn_id") or "")


def latest_advisor_tool_context(
    store: ReceiptStore,
    *,
    session_id: str,
    tool_name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    phase = str(args.get("phase") or "")
    for entry in reversed(store.read_all()):
        if (
            entry.get("session_id") != session_id
            or entry.get("source") != "pre_tool_call"
            or entry.get("event") != "advisor_tool_context"
        ):
            continue
        extra = entry.get("extra")
        if not isinstance(extra, dict) or extra.get("tool_name") != tool_name:
            continue
        raw_args = extra.get("args")
        if phase and isinstance(raw_args, dict) and str(raw_args.get("phase") or "") != phase:
            continue
        return dict(extra)
    return {}


def merge_call_context(
    explicit_context: dict[str, Any],
    fallback_context: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(fallback_context)
    merged.update(
        {key: value for key, value in explicit_context.items() if value not in (None, "")}
    )
    return cast(dict[str, Any], redact_secrets(merged))


def result_from_receipt_entry(entry: dict[str, Any]) -> AdvisorResult | None:
    try:
        return result_from_dict(
            {
                "phase": entry["phase"],
                "verdict": entry["verdict"],
                "findings": entry.get("findings", []),
                "known_unresolved": entry.get("known_unresolved", []),
                "degraded": entry.get("degraded", False),
                "error_class": entry.get("error_class"),
                "diagnostics": entry.get("diagnostics", []),
                "unavailable_reason": entry.get("unavailable_reason", ""),
                "final_improvement": entry.get("final_improvement", ""),
            }
        )
    except (KeyError, ValueError):
        return None


def latest_passed_audit_index(
    store: ReceiptStore,
    *,
    session_id: str,
    phase: AdvisorPhase,
    turn_id: str = "",
) -> int | None:
    for index, entry in reversed(list(enumerate(store.read_all()))):
        if entry.get("session_id") != session_id or entry.get("phase") != phase.value:
            continue
        if turn_id and entry_turn_id(entry) != turn_id:
            continue
        if is_gate_passed(result_from_receipt_entry(entry)):
            return index
    return None


def entry_final_audit_matches_response(entry: dict[str, Any], final_response: str) -> bool:
    extra = entry.get("extra")
    packet = extra.get("packet") if isinstance(extra, dict) else None
    if not isinstance(packet, dict):
        return False
    audited_draft = str(packet.get("final_answer_draft") or "").strip()
    return bool(audited_draft) and audited_draft == str(final_response or "").strip()


def latest_resolution_gate_after_final_audit(
    store: ReceiptStore,
    *,
    session_id: str,
    audit_index: int | None = None,
) -> ResolutionGate | None:
    audit = (
        (audit_index, {})
        if audit_index is not None
        else latest_indexed_entry(store, session_id=session_id, phase=AdvisorPhase.A3_FINAL.value)
    )
    gate = latest_indexed_entry(store, session_id=session_id, phase="RESOLUTION_GATE")
    if audit is None or gate is None or gate[0] <= audit[0]:
        return None
    raw_gate = gate[1].get("resolution_gate")
    if not isinstance(raw_gate, dict):
        return None
    try:
        return resolution_gate_from_dict(raw_gate)
    except ValueError:
        return None


def latest_final_relevant_event_index(store: ReceiptStore, *, session_id: str) -> int:
    latest = -1
    for index, entry in enumerate(store.read_all()):
        if entry.get("session_id") != session_id:
            continue
        source = str(entry.get("source") or "")
        phase = str(entry.get("phase") or "")
        if "verdict" in entry and phase in {
            AdvisorPhase.A1_PLAN.value,
            AdvisorPhase.A2_DELEGATION.value,
            AdvisorPhase.A3_EXCEPTION.value,
        }:
            latest = index
            continue
        if source in {"subagent_start", "subagent_stop"}:
            latest = index
            continue
        if source == "post_tool_call":
            extra = entry.get("extra")
            tool_name = ""
            if isinstance(extra, dict):
                tool_name = str(extra.get("tool_name") or "")
            if tool_name not in ADVISOR_TOOL_NAMES:
                latest = index
    return latest


def latest_current_final_audit(
    store: ReceiptStore,
    *,
    session_id: str,
    final_response: str,
) -> tuple[int, AdvisorResult] | None:
    min_index = latest_final_relevant_event_index(store, session_id=session_id)
    for index, entry in reversed(list(enumerate(store.read_all()))):
        if (
            entry.get("session_id") != session_id
            or entry.get("phase") != AdvisorPhase.A3_FINAL.value
            or index <= min_index
        ):
            continue
        result = result_from_receipt_entry(entry)
        if (
            result is not None
            and is_gate_passed(result)
            and entry_final_audit_matches_response(entry, final_response)
        ):
            return index, result
    return None


def latest_unresolved_exception_event(
    store: ReceiptStore,
    *,
    session_id: str,
) -> dict[str, Any] | None:
    latest_passed_audit_index = -1
    latest_exception_event: tuple[int, dict[str, Any]] | None = None
    for index, entry in enumerate(store.read_all()):
        if entry.get("session_id") != session_id:
            continue
        if entry.get("phase") == AdvisorPhase.A3_EXCEPTION.value:
            result = result_from_receipt_entry(entry)
            if is_gate_passed(result):
                latest_passed_audit_index = index
        extra = entry.get("extra")
        if (
            entry.get("source") == "post_tool_call"
            and entry.get("event") == "post_tool_call"
            and isinstance(extra, dict)
            and extra.get("requires_a3_exception") is True
        ):
            latest_exception_event = (index, entry)
    if latest_exception_event is None:
        return None
    if latest_exception_event[0] <= latest_passed_audit_index:
        return None
    return latest_exception_event[1]
