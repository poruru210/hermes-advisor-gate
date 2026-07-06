"""Final and verification gates for Advisor Gate."""

from __future__ import annotations

from typing import Any

from advisor_gate.config import AdvisorGateConfig
from advisor_gate.policy import build_gate_message, is_gate_passed
from advisor_gate.receipt_queries import (
    latest_current_final_audit,
    latest_resolution_gate_after_final_audit,
    latest_unresolved_exception_event,
)
from advisor_gate.schemas import AdvisorPhase, ResolutionDecision
from advisor_gate.store import ReceiptStore


def _exception_gate_message(exception_event: dict[str, Any]) -> str:
    extra = exception_event.get("extra")
    if not isinstance(extra, dict):
        extra = {}
    tool_name = str(extra.get("tool_name") or "unknown")
    error_type = str(extra.get("error_type") or "tool_error")
    preview = str(extra.get("result_preview") or "").strip()
    if len(preview) > 800:
        preview = preview[:800] + "..."
    return (
        "Run advisor_audit for A3_EXCEPTION before final delivery. A tool, "
        "runtime, model, or subagent failure was observed after the latest "
        "passing A3_EXCEPTION audit.\n\n"
        f"Tool: {tool_name}\n"
        f"Error type/status: {error_type}\n"
        f"Evidence preview:\n{preview}"
    )


def on_transform_llm_output(
    store: ReceiptStore,
    config: AdvisorGateConfig,
    *,
    response_text: str,
    session_id: str,
    **kwargs: Any,
) -> str | None:
    del kwargs
    if not config.enabled or not config.require_a3_final or not session_id:
        return None
    if not config.gate_subagents and store.is_child_session(session_id):
        return None
    if config.defer_while_subagents_active and store.has_active_child_session(session_id):
        active = ", ".join(store.active_child_sessions(session_id))
        return (
            "Advisor Gate: CHANGES_REQUIRED\n\n"
            "Background subagent work is still active. Do not deliver a final "
            f"answer yet; wait for subagent completion and include receipts. Active: {active}"
        )
    if config.require_a3_exception:
        exception_event = latest_unresolved_exception_event(store, session_id=session_id)
        if exception_event is not None:
            return "Advisor Gate: CHANGES_REQUIRED\n\n" + _exception_gate_message(exception_event)
    current_final = latest_current_final_audit(
        store,
        session_id=session_id,
        final_response=response_text,
    )
    latest = store.latest_result(session_id=session_id, phase=AdvisorPhase.A3_FINAL)
    if current_final is not None:
        final_audit_index, latest = current_final
        if not config.require_resolution_gate:
            return None
        resolution_gate = latest_resolution_gate_after_final_audit(
            store,
            session_id=session_id,
            audit_index=final_audit_index,
        )
        if (
            resolution_gate is not None
            and resolution_gate.commander_decision is ResolutionDecision.CONTINUE
            and not resolution_gate.open_findings
        ):
            return None
        return (
            "Advisor Gate: CHANGES_REQUIRED\n\n"
            "A3_FINAL passed, but the Commander resolution gate is missing or "
            "still has open findings. Run advisor_resolution_gate with "
            "commander_decision='continue' and explicit finding resolutions, "
            "after the current A3_FINAL audit before final delivery."
        )
    if latest is not None and is_gate_passed(latest):
        return (
            "Advisor Gate: CHANGES_REQUIRED\n\n"
            "The latest A3_FINAL receipt is stale or does not match this final "
            "response draft. Run advisor_audit again with a FinalPayload whose "
            "final_answer_draft exactly matches the response to be delivered, "
            "after the latest tool/subagent/exception event."
        )
    return build_gate_message(latest, missing_final=latest is None)


def on_final_delivery_gate(
    store: ReceiptStore,
    config: AdvisorGateConfig,
    *,
    response_text: str = "",
    final_response: str = "",
    session_id: str,
    changed_paths: list[str] | None = None,
    **kwargs: Any,
) -> dict[str, str] | None:
    del response_text, kwargs
    if not config.enabled or not config.require_a3_final or not session_id:
        return None
    if not config.gate_subagents and store.is_child_session(session_id):
        return None
    if config.defer_while_subagents_active and store.has_active_child_session(session_id):
        active = ", ".join(store.active_child_sessions(session_id))
        return {
            "action": "continue",
            "message": (
                "Background subagent work is still active. Do not deliver a final "
                "answer yet; wait for subagent completion and then run the "
                f"required Advisor audits. Active: {active}"
            ),
        }
    if config.require_a3_exception:
        exception_event = latest_unresolved_exception_event(store, session_id=session_id)
        if exception_event is not None:
            return {
                "action": "continue",
                "message": _exception_gate_message(exception_event),
            }
    current_final = latest_current_final_audit(
        store,
        session_id=session_id,
        final_response=final_response,
    )
    latest = store.latest_result(session_id=session_id, phase=AdvisorPhase.A3_FINAL)
    if current_final is None:
        paths = ", ".join(changed_paths or [])
        message = (
            "Run advisor_audit for A3_FINAL before final delivery. The packet must "
            "use the FinalPayload shape: actions_taken, tests_or_checks, "
            "known_unresolved, final_answer_draft, and flow_summary. Include "
            f"changed paths ({paths}), subagent/tool receipts, and this final draft:\n\n"
            + (final_response or "")[:4000]
        )
        if latest is not None:
            message += (
                "\n\nThe latest A3_FINAL receipt is missing, failing, or was "
                "created for a different final_answer_draft or before the latest "
                "tool/subagent/exception event."
            )
        return {"action": "continue", "message": message}

    if not config.require_resolution_gate:
        return None
    final_audit_index, latest = current_final
    resolution_gate = latest_resolution_gate_after_final_audit(
        store,
        session_id=session_id,
        audit_index=final_audit_index,
    )
    if (
        resolution_gate is not None
        and resolution_gate.commander_decision is ResolutionDecision.CONTINUE
        and not resolution_gate.open_findings
    ):
        return None

    findings = []
    for finding in latest.findings:
        findings.append(
            f"- {finding.finding_id}: {finding.message} "
            f"(required: {finding.recommended_action})"
        )
    finding_text = "\n".join(findings) if findings else "- No Advisor findings; record continue."
    return {
        "action": "continue",
        "message": (
            "Record the Commander resolution gate before final delivery by "
            "calling advisor_resolution_gate. Each Advisor finding must be "
            "accepted, resolved, deferred, or rejected with a reason and evidence. "
            "Use commander_decision='continue' only when open_findings is empty.\n\n"
            f"Latest A3_FINAL findings:\n{finding_text}"
        ),
    }


def on_pre_verify(
    store: ReceiptStore,
    config: AdvisorGateConfig,
    *,
    session_id: str,
    final_response: str = "",
    changed_paths: list[str] | None = None,
    **kwargs: Any,
) -> dict[str, str] | None:
    del kwargs
    if not config.enabled or not config.require_a3_final or not session_id:
        return None
    if not config.gate_subagents and store.is_child_session(session_id):
        return None
    if config.defer_while_subagents_active and store.has_active_child_session(session_id):
        active = ", ".join(store.active_child_sessions(session_id))
        return {
            "action": "continue",
            "message": (
                "Background subagent work is still active. Wait for subagent "
                f"completion before final verification. Active: {active}"
            ),
        }
    if config.require_a3_exception:
        exception_event = latest_unresolved_exception_event(store, session_id=session_id)
        if exception_event is not None:
            return {
                "action": "continue",
                "message": _exception_gate_message(exception_event),
            }
    current_final = latest_current_final_audit(
        store,
        session_id=session_id,
        final_response=final_response,
    )
    latest = store.latest_result(session_id=session_id, phase=AdvisorPhase.A3_FINAL)
    if current_final is not None:
        final_audit_index, latest = current_final
        if config.require_resolution_gate:
            resolution_gate = latest_resolution_gate_after_final_audit(
                store,
                session_id=session_id,
                audit_index=final_audit_index,
            )
            if (
                resolution_gate is None
                or resolution_gate.commander_decision is not ResolutionDecision.CONTINUE
                or resolution_gate.open_findings
            ):
                findings = []
                for finding in latest.findings:
                    findings.append(
                        f"- {finding.finding_id}: {finding.message} "
                        f"(required: {finding.recommended_action})"
                    )
                finding_text = (
                    "\n".join(findings)
                    if findings
                    else "- No Advisor findings; record continue."
                )
                return {
                    "action": "continue",
                    "message": (
                        "Record advisor_resolution_gate before finishing. "
                        "Use commander_decision='continue' only when open_findings "
                        "is empty.\n\n"
                        f"Latest A3_FINAL findings:\n{finding_text}"
                    ),
                }
        return None
    paths = ", ".join(changed_paths or [])
    message = (
        "Run advisor_audit for A3_FINAL before finishing. Include the final draft, "
        f"changed paths ({paths}), verification evidence, known_unresolved, and "
        "any subagent/tool receipts. Resolve CHANGES_REQUIRED or BLOCK findings."
    )
    if final_response:
        message += "\n\nPremature final draft to audit:\n" + final_response[:4000]
    if latest is not None:
        message += (
            "\n\nThe latest A3_FINAL receipt is missing, failing, or was "
            "created for a different final_answer_draft or before the latest "
            "tool/subagent/exception event."
        )
    return {"action": "continue", "message": message}
