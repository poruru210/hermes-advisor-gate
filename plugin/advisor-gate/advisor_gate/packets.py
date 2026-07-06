"""Prompt packet builders for Advisor audit phases."""

from __future__ import annotations

import json
from typing import Any

from .prompts import ADVISOR_SYSTEM_PROMPT, PHASE_INSTRUCTIONS
from .schemas import (
    AdvisorPhase,
    delegation_payload_from_dict,
    delegation_payload_to_dict,
    final_payload_from_dict,
    final_payload_to_dict,
    plan_payload_from_dict,
    plan_payload_to_dict,
)


def build_prompt_packet(phase: AdvisorPhase | str, payload: dict[str, Any]) -> dict[str, Any]:
    phase_value = AdvisorPhase(str(phase)).value
    if not isinstance(payload, dict):
        raise ValueError("packet payload must be an object")
    return {
        "phase": phase_value,
        "instructions": PHASE_INSTRUCTIONS[phase_value],
        "payload": payload,
        "required_output": "AdvisorResult JSON object",
    }


def build_advisor_structured_input(
    phase: AdvisorPhase | str,
    payload: dict[str, Any],
) -> tuple[str, list[dict[str, str]]]:
    packet = build_prompt_packet(phase, payload)
    instructions = (
        f"{ADVISOR_SYSTEM_PROMPT}\n\n"
        f"Phase: {packet['phase']}\n"
        f"Audit focus: {packet['instructions']}\n"
        "Return only the AdvisorResult JSON object."
    )
    return instructions, [{"type": "text", "text": json.dumps(packet, ensure_ascii=False)}]


def build_plan_packet(
    *,
    user_message: str,
    commander_interpretation: str,
    task_plan: list[dict[str, Any]] | list[str],
    coverage_table: list[dict[str, Any]] | list[str],
    risk_level: str,
    constraints: list[str] | None = None,
    source_evidence: list[dict[str, Any]] | list[str] | None = None,
    known_unresolved: list[str] | None = None,
) -> dict[str, Any]:
    payload = plan_payload_from_dict(
        {
            "user_message": user_message,
            "commander_interpretation": commander_interpretation,
            "task_plan": task_plan,
            "coverage_table": coverage_table,
            "risk_level": risk_level,
            "constraints": constraints or [],
            "source_evidence": source_evidence or [],
            "known_unresolved": known_unresolved or [],
        }
    )
    return plan_payload_to_dict(payload)


def build_delegation_packet(
    *,
    commander_plan: str,
    worker_assignments: list[dict[str, Any]],
    empty_result_policy: str,
    risk_level: str,
    handoff_expectations: str = "",
    known_unresolved: list[str] | None = None,
) -> dict[str, Any]:
    payload = delegation_payload_from_dict(
        {
            "commander_plan": commander_plan,
            "worker_assignments": worker_assignments,
            "empty_result_policy": empty_result_policy,
            "risk_level": risk_level,
            "handoff_expectations": handoff_expectations,
            "known_unresolved": known_unresolved or [],
        }
    )
    return delegation_payload_to_dict(payload)


def build_final_packet(
    *,
    actions_taken: list[dict[str, Any]] | list[str],
    tests_or_checks: list[dict[str, Any]] | list[str],
    known_unresolved: list[str],
    final_answer_draft: str,
    flow_summary: str,
) -> dict[str, Any]:
    payload = final_payload_from_dict(
        {
            "actions_taken": actions_taken,
            "tests_or_checks": tests_or_checks,
            "known_unresolved": known_unresolved,
            "final_answer_draft": final_answer_draft,
            "flow_summary": flow_summary,
        }
    )
    return final_payload_to_dict(payload)
