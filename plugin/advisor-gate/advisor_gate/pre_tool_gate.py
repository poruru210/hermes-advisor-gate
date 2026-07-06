"""A1/A2 pre-tool gate for Advisor Gate."""

from __future__ import annotations

from typing import Any

from advisor_gate.config import AdvisorGateConfig
from advisor_gate.receipt_queries import latest_passed_audit_index
from advisor_gate.schemas import AdvisorPhase
from advisor_gate.store import ReceiptStore, redact_secrets, utc_now_iso
from advisor_gate.tool_schemas import ADVISOR_TOOL_NAMES


def _effective_session_id(*values: Any) -> str:
    for value in values:
        if value:
            return str(value)
    return ""


def _action_tool_names(config: AdvisorGateConfig) -> set[str]:
    return {name for name in config.a1_action_tool_names if name}


def _exempt_tool_names(config: AdvisorGateConfig) -> set[str]:
    return {name for name in config.a1_exempt_tool_names if name}


def _exempt_tool_prefixes(config: AdvisorGateConfig) -> tuple[str, ...]:
    return tuple(prefix for prefix in config.a1_exempt_tool_prefixes if prefix)


def _tool_requires_a1(config: AdvisorGateConfig, tool_name: str) -> bool:
    if tool_name in _action_tool_names(config):
        return True
    if tool_name in _exempt_tool_names(config):
        return False
    if any(tool_name.startswith(prefix) for prefix in _exempt_tool_prefixes(config)):
        return False
    return config.gate_unclassified_tools_before_a1


def _append_advisor_tool_context(
    store: ReceiptStore,
    *,
    session_id: str,
    tool_name: str,
    kwargs: dict[str, Any],
) -> None:
    raw_args = kwargs.get("args") or kwargs.get("arguments") or {}
    args = raw_args if isinstance(raw_args, dict) else {}
    store.append(
        {
            "timestamp": utc_now_iso(),
            "source": "pre_tool_call",
            "session_id": session_id,
            "phase": str(args.get("phase") or "ADVISOR_TOOL"),
            "event": "advisor_tool_context",
            "extra": redact_secrets(
                {
                    "tool_name": tool_name,
                    "args": args,
                    "turn_id": kwargs.get("turn_id"),
                    "task_id": kwargs.get("task_id"),
                    "tool_call_id": kwargs.get("tool_call_id"),
                    "api_request_id": kwargs.get("api_request_id"),
                }
            ),
        }
    )


def _append_blocked_pre_tool_call(
    store: ReceiptStore,
    *,
    session_id: str,
    phase: AdvisorPhase,
    tool_name: str,
    reason: str,
    kwargs: dict[str, Any],
) -> None:
    store.append(
        {
            "timestamp": utc_now_iso(),
            "source": "pre_tool_call",
            "session_id": session_id,
            "phase": phase.value,
            "event": "blocked_tool_call",
            "extra": redact_secrets(
                {
                    "tool_name": tool_name,
                    "reason": reason,
                    "args": kwargs.get("args") or kwargs.get("arguments"),
                    "turn_id": kwargs.get("turn_id"),
                    "task_id": kwargs.get("task_id"),
                }
            ),
        }
    )


def _block_pre_tool_call_message(
    *,
    phase: AdvisorPhase,
    tool_name: str,
    reason: str,
) -> dict[str, str]:
    if phase is AdvisorPhase.A1_PLAN:
        packet_hint = (
            "Run advisor_audit with phase='A1_PLAN' before this action. The packet "
            "should include user_message, commander_interpretation, task_plan, "
            "coverage_table, and risk_level."
        )
    else:
        packet_hint = (
            "Run advisor_audit with phase='A2_DELEGATION' before delegating work. "
            "The packet should include the Commander plan, Worker scope, expected "
            "evidence, exception/final handoff expectations, and risk_level."
        )
    return {
        "action": "block",
        "message": (
            "Advisor Gate: CHANGES_REQUIRED\n\n"
            f"Tool `{tool_name}` is blocked by {phase.value}: {reason}\n\n"
            f"{packet_hint}"
        ),
    }


def on_pre_tool_call(
    store: ReceiptStore,
    config: AdvisorGateConfig,
    *,
    tool_name: str,
    session_id: str = "",
    task_id: str = "",
    **kwargs: Any,
) -> dict[str, str] | None:
    if not config.enabled:
        return None
    tool_name = str(tool_name or "").strip()
    if not tool_name:
        return None
    effective_session = _effective_session_id(session_id, task_id, kwargs.get("task_id"))
    if not effective_session:
        return None
    if tool_name in ADVISOR_TOOL_NAMES:
        _append_advisor_tool_context(
            store,
            session_id=effective_session,
            tool_name=tool_name,
            kwargs={**kwargs, "task_id": task_id},
        )
        return None
    if not config.gate_subagents and store.is_child_session(effective_session):
        return None

    turn_id = str(kwargs.get("turn_id") or "")
    if config.require_a1_before_action and _tool_requires_a1(config, tool_name):
        latest_a1_index = latest_passed_audit_index(
            store,
            session_id=effective_session,
            phase=AdvisorPhase.A1_PLAN,
            turn_id=turn_id,
        )
        if latest_a1_index is None:
            reason = (
                "A1_PLAN has not passed for this turn."
                if turn_id
                else "A1_PLAN has not passed for this session."
            )
            _append_blocked_pre_tool_call(
                store,
                session_id=effective_session,
                phase=AdvisorPhase.A1_PLAN,
                tool_name=tool_name,
                reason=reason,
                kwargs={**kwargs, "task_id": task_id},
            )
            return _block_pre_tool_call_message(
                phase=AdvisorPhase.A1_PLAN,
                tool_name=tool_name,
                reason=reason,
            )

    if config.require_a2_before_delegation and tool_name == "delegate_task":
        latest_a2_index = latest_passed_audit_index(
            store,
            session_id=effective_session,
            phase=AdvisorPhase.A2_DELEGATION,
            turn_id=turn_id,
        )
        if latest_a2_index is None:
            reason = (
                "A2_DELEGATION has not passed for this turn before delegation."
                if turn_id
                else "A2_DELEGATION has not passed before delegation."
            )
            _append_blocked_pre_tool_call(
                store,
                session_id=effective_session,
                phase=AdvisorPhase.A2_DELEGATION,
                tool_name=tool_name,
                reason=reason,
                kwargs={**kwargs, "task_id": task_id},
            )
            return _block_pre_tool_call_message(
                phase=AdvisorPhase.A2_DELEGATION,
                tool_name=tool_name,
                reason=reason,
            )

    return None
