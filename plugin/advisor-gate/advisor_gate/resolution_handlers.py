"""Commander resolution gate tool handler."""

from __future__ import annotations

import json
from typing import Any, cast

from advisor_gate.config import AdvisorGateConfig, load_plugin_config
from advisor_gate.receipt_queries import latest_advisor_tool_context, merge_call_context
from advisor_gate.schemas import (
    ResolutionDecision,
    ResolutionGate,
    resolution_gate_from_dict,
    resolution_gate_to_dict,
)
from advisor_gate.store import ReceiptStore, redact_secrets
from advisor_gate.tool_schemas import RESOLUTION_TOOL_NAME


def advisor_resolution_gate_handler(
    args: dict[str, Any],
    *,
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
            tool_name=RESOLUTION_TOOL_NAME,
            args=args,
        ),
    )
    try:
        if not config.enabled:
            raise RuntimeError("advisor_gate.enabled is false")
        gate = resolution_gate_from_dict(args)
    except Exception as exc:
        gate = ResolutionGate(
            commander_decision=ResolutionDecision.REQUIRES_RESOLUTION,
            reason=f"Invalid resolution gate: {exc}",
            open_findings=("F-RESOLUTION-GATE-INVALID",),
        )
    store.append_resolution_gate(
        session_id=effective_session,
        gate=gate,
        source=RESOLUTION_TOOL_NAME,
        extra={"raw": redact_secrets(args), "call_context": call_context},
    )
    payload = resolution_gate_to_dict(gate)
    payload["policy_action"] = (
        "continue"
        if gate.commander_decision is ResolutionDecision.CONTINUE
        else "requires_resolution"
    )
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
