"""Advisor audit tool handler."""

from __future__ import annotations

import json
from typing import Any, cast

from advisor_gate.config import AdvisorGateConfig, load_plugin_config
from advisor_gate.packets import build_advisor_structured_input
from advisor_gate.policy import decide_action
from advisor_gate.receipt_queries import latest_advisor_tool_context, merge_call_context
from advisor_gate.schemas import (
    AdvisorPhase,
    AdvisorResult,
    AdvisorVerdict,
    Finding,
    FindingCategory,
    Severity,
    advisor_result_json_schema,
    final_payload_from_dict,
    result_from_dict,
    result_to_dict,
)
from advisor_gate.store import ReceiptStore, redact_secrets
from advisor_gate.tool_schemas import TOOL_NAME


def _error_result(phase: AdvisorPhase, message: str, error_class: str) -> AdvisorResult:
    return AdvisorResult(
        phase=phase,
        verdict=AdvisorVerdict.CHANGES_REQUIRED,
        findings=(
            Finding(
                finding_id="F-DEGRADED-001",
                severity=Severity.MEDIUM,
                category=FindingCategory.EXCEPTION,
                message=message,
                recommended_action="Retry the Advisor audit or record this as known_unresolved.",
                acceptance_check="A valid AdvisorResult receipt exists for the requested phase.",
            ),
        ),
        known_unresolved=(message,),
        degraded=True,
        error_class=error_class,
        diagnostics=(message,),
        unavailable_reason=message,
    )


def _validate_audit_packet(phase: AdvisorPhase, packet: dict[str, Any]) -> None:
    if phase is AdvisorPhase.A3_FINAL:
        final_payload_from_dict(packet)


def _coerce_llm_result(raw: Any, phase: AdvisorPhase) -> AdvisorResult:
    parsed = getattr(raw, "parsed", None)
    if parsed is None and isinstance(raw, dict):
        parsed = raw
    if parsed is None:
        text = getattr(raw, "text", "")
        if isinstance(text, str) and text.strip():
            parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Advisor LLM did not return a JSON object")
    parsed = dict(parsed)
    parsed.setdefault("phase", phase.value)
    return result_from_dict(parsed)


def _phase_from_args(
    args: dict[str, Any],
    default: AdvisorPhase = AdvisorPhase.A3_EXCEPTION,
) -> AdvisorPhase:
    try:
        return AdvisorPhase(str(args.get("phase", default.value)))
    except ValueError:
        return default


def run_advisor_audit(
    *,
    phase: AdvisorPhase,
    packet: dict[str, Any],
    llm: Any,
    config: AdvisorGateConfig,
) -> AdvisorResult:
    instructions, input_blocks = build_advisor_structured_input(phase, packet)
    kwargs: dict[str, Any] = {
        "instructions": instructions,
        "input": input_blocks,
        "json_schema": advisor_result_json_schema(),
        "schema_name": "AdvisorResult",
        "purpose": f"advisor-gate.{phase.value.lower()}",
        "temperature": 0.0,
        "max_tokens": 1200,
    }
    if config.provider:
        kwargs["provider"] = config.provider
    if config.model:
        kwargs["model"] = config.model
    raw = llm.complete_structured(**kwargs)
    return _coerce_llm_result(raw, phase)


def advisor_audit_handler(
    args: dict[str, Any],
    *,
    ctx: Any | None = None,
    llm: Any | None = None,
    store: ReceiptStore | None = None,
    config: AdvisorGateConfig | None = None,
    session_id: str = "",
    **kwargs: Any,
) -> str:
    config = config or load_plugin_config()
    store = store or ReceiptStore.from_path(config.receipt_path)
    effective_session = str(args.get("session_id") or session_id or "")
    call_context = merge_call_context(
        cast(dict[str, Any], redact_secrets(kwargs)),
        latest_advisor_tool_context(
            store,
            session_id=effective_session,
            tool_name=TOOL_NAME,
            args=args,
        ),
    )
    try:
        phase = AdvisorPhase(str(args.get("phase")))
        packet = args.get("packet")
        if not isinstance(packet, dict):
            raise ValueError("packet must be an object")
        if not config.enabled:
            raise RuntimeError("advisor_gate.enabled is false")
        packet = cast(dict[str, Any], redact_secrets(packet))
        _validate_audit_packet(phase, packet)
        packet_size = len(json.dumps(packet, ensure_ascii=False, sort_keys=True))
        if config.max_input_chars > 0 and packet_size > config.max_input_chars:
            raise ValueError(
                f"packet is too large for advisor_gate.max_input_chars "
                f"({packet_size} > {config.max_input_chars})"
            )
        effective_llm = llm if llm is not None else getattr(ctx, "llm", None)
        if effective_llm is None:
            raise RuntimeError("Hermes ctx.llm is unavailable")
        result = run_advisor_audit(
            phase=phase,
            packet=packet,
            llm=effective_llm,
            config=config,
        )
    except Exception as exc:
        phase = _phase_from_args(args)
        result = _error_result(phase, str(exc), exc.__class__.__name__)

    store.append_result(
        session_id=effective_session,
        result=result,
        source=TOOL_NAME,
        extra={
            "packet": redact_secrets(args.get("packet", {})),
            "call_context": call_context,
        },
    )
    payload = result_to_dict(result)
    payload["policy_action"] = decide_action(result).value
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
