"""Hermes tool names and JSON schemas for Advisor Gate."""

from __future__ import annotations

from advisor_gate.schemas import AdvisorPhase, ResolutionDecision

TOOL_NAME = "advisor_audit"
RESOLUTION_TOOL_NAME = "advisor_resolution_gate"
ADVISOR_TOOL_NAMES = {TOOL_NAME, RESOLUTION_TOOL_NAME}

ADVISOR_AUDIT_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Run a review-only Advisor Gate audit for A1_PLAN, A2_DELEGATION, "
        "A3_EXCEPTION, or A3_FINAL. The Advisor must not execute tools or modify files."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "phase": {
                "type": "string",
                "enum": [phase.value for phase in AdvisorPhase],
                "description": "Advisor audit phase.",
            },
            "packet": {
                "type": "object",
                "description": (
                    "Evidence packet to audit. Include task, plan/final draft, "
                    "evidence, receipts, and known_unresolved as appropriate."
                ),
            },
            "session_id": {
                "type": "string",
                "description": "Optional session id. Hermes passes one when available.",
            },
        },
        "required": ["phase", "packet"],
    },
}

ADVISOR_RESOLUTION_GATE_SCHEMA = {
    "name": RESOLUTION_TOOL_NAME,
    "description": (
        "Record the Commander's resolution decision for Advisor findings. "
        "Use this after A3_FINAL before final delivery."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "commander_decision": {
                "type": "string",
                "enum": [item.value for item in ResolutionDecision],
                "description": "continue only when no open findings remain.",
            },
            "reason": {
                "type": "string",
                "description": "Why the Commander can continue or what remains unresolved.",
            },
            "open_findings": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Finding IDs still open. Must be empty for continue.",
            },
            "resolutions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "finding_id": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["accepted", "resolved", "deferred", "rejected"],
                        },
                        "reason": {"type": "string"},
                        "evidence": {"type": "string"},
                    },
                    "required": ["finding_id", "status", "reason"],
                },
            },
            "session_id": {
                "type": "string",
                "description": "Optional session id. Hermes passes one when available.",
            },
        },
        "required": ["commander_decision", "reason", "open_findings", "resolutions"],
    },
}
