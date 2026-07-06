"""Prompt packet builders for Advisor audit phases."""

from __future__ import annotations

import json
from typing import Any

from advisor_gate.prompts import ADVISOR_SYSTEM_PROMPT, PHASE_INSTRUCTIONS
from advisor_gate.schemas import AdvisorPhase, final_payload_from_dict, final_payload_to_dict


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
    task: str,
    plan: str,
    constraints: list[str],
    evidence: list[str],
) -> dict[str, Any]:
    return {
        "task": task,
        "plan": plan,
        "constraints": constraints,
        "evidence": evidence,
    }


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
