"""Policy decisions for Advisor Gate results."""

from __future__ import annotations

from enum import StrEnum

from advisor_gate.schemas import AdvisorResult, AdvisorVerdict, Severity, validate_result


class PolicyAction(StrEnum):
    CONTINUE = "continue"
    REQUIRES_RESOLUTION = "requires_resolution"
    STOP = "stop"


def decide_action(result: AdvisorResult) -> PolicyAction:
    validate_result(result)
    if result.verdict is AdvisorVerdict.BLOCK:
        return PolicyAction.STOP
    if result.verdict is AdvisorVerdict.CHANGES_REQUIRED:
        return PolicyAction.REQUIRES_RESOLUTION
    if result.degraded:
        return PolicyAction.REQUIRES_RESOLUTION
    if any(finding.severity is Severity.HIGH for finding in result.findings):
        return PolicyAction.REQUIRES_RESOLUTION
    return PolicyAction.CONTINUE


def is_gate_passed(result: AdvisorResult | None) -> bool:
    return result is not None and decide_action(result) is PolicyAction.CONTINUE


def build_gate_message(result: AdvisorResult | None, *, missing_final: bool = False) -> str:
    if result is None or missing_final:
        return (
            "Advisor Gate: CHANGES_REQUIRED\n\n"
            "A3_FINAL audit receipt is missing for this session. Run advisor_audit "
            "for phase A3_FINAL with the final draft, evidence, known unresolved "
            "items, and any subagent receipts before claiming completion."
        )

    action = decide_action(result)
    if action is PolicyAction.CONTINUE:
        return ""

    lines = [f"Advisor Gate: {result.verdict.value}", "", f"Phase: {result.phase.value}"]
    if result.degraded:
        lines.append("State: degraded")
    if result.error_class:
        lines.append(f"Error: {result.error_class}")
    if result.known_unresolved:
        lines.append("")
        lines.append("Known unresolved:")
        lines.extend(f"- {item}" for item in result.known_unresolved)
    if result.findings:
        lines.append("")
        lines.append("Findings:")
        for finding in result.findings:
            lines.append(f"- {finding.finding_id} [{finding.severity.value}] {finding.message}")
            lines.append(f"  Required: {finding.recommended_action}")
            lines.append(f"  Check: {finding.acceptance_check}")
    if action is PolicyAction.STOP:
        lines.append("")
        lines.append("Do not proceed until the BLOCK finding is resolved.")
    return "\n".join(lines)
