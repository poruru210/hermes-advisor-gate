"""Schemas and validation for Advisor Gate results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, TypeVar

EnumT = TypeVar("EnumT", bound=StrEnum)


class AdvisorPhase(StrEnum):
    A1_PLAN = "A1_PLAN"
    A2_DELEGATION = "A2_DELEGATION"
    A3_EXCEPTION = "A3_EXCEPTION"
    A3_FINAL = "A3_FINAL"


class AdvisorVerdict(StrEnum):
    PASS = "PASS"
    CHANGES_REQUIRED = "CHANGES_REQUIRED"
    BLOCK = "BLOCK"


class ResolutionDecision(StrEnum):
    CONTINUE = "continue"
    REQUIRES_RESOLUTION = "requires_resolution"


class FindingResolutionStatus(StrEnum):
    ACCEPTED = "accepted"
    RESOLVED = "resolved"
    DEFERRED = "deferred"
    REJECTED = "rejected"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FindingCategory(StrEnum):
    EVIDENCE_GAP = "evidence_gap"
    PLAN_GAP = "plan_gap"
    DELEGATION_GAP = "delegation_gap"
    EXCEPTION = "exception"
    FINAL_QUALITY = "final_quality"
    SAFETY = "safety"
    OTHER = "other"


@dataclass(frozen=True)
class Finding:
    finding_id: str
    severity: Severity
    category: FindingCategory
    message: str
    recommended_action: str
    acceptance_check: str
    evidence_quote: str = ""


@dataclass(frozen=True)
class AdvisorResult:
    phase: AdvisorPhase
    verdict: AdvisorVerdict
    findings: tuple[Finding, ...] = field(default_factory=tuple)
    known_unresolved: tuple[str, ...] = field(default_factory=tuple)
    degraded: bool = False
    error_class: str | None = None
    diagnostics: tuple[str, ...] = field(default_factory=tuple)
    unavailable_reason: str = ""
    final_improvement: str = ""


@dataclass(frozen=True)
class FindingResolution:
    finding_id: str
    status: FindingResolutionStatus
    reason: str
    evidence: str = ""


@dataclass(frozen=True)
class ResolutionGate:
    commander_decision: ResolutionDecision
    reason: str
    open_findings: tuple[str, ...] = field(default_factory=tuple)
    resolutions: tuple[FindingResolution, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class FinalPayload:
    actions_taken: tuple[dict[str, Any], ...]
    tests_or_checks: tuple[dict[str, Any], ...]
    known_unresolved: tuple[str, ...]
    final_answer_draft: str
    flow_summary: str


@dataclass(frozen=True)
class PlanPayload:
    user_message: str
    commander_interpretation: str
    task_plan: tuple[dict[str, Any], ...]
    coverage_table: tuple[dict[str, Any], ...]
    risk_level: str
    constraints: tuple[str, ...] = field(default_factory=tuple)
    source_evidence: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    known_unresolved: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class WorkerAssignment:
    worker_id: str
    child_role: str
    scope: str
    expected_evidence: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class DelegationPayload:
    commander_plan: str
    worker_assignments: tuple[WorkerAssignment, ...]
    empty_result_policy: str
    risk_level: str
    handoff_expectations: str = ""
    known_unresolved: tuple[str, ...] = field(default_factory=tuple)


def _coerce_enum(enum_type: type[EnumT], value: Any, field_name: str) -> EnumT:
    try:
        return enum_type(str(value))
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(f"{field_name} must be one of: {allowed}") from exc


def finding_from_dict(raw: dict[str, Any]) -> Finding:
    required = [
        "finding_id",
        "severity",
        "category",
        "message",
        "recommended_action",
        "acceptance_check",
    ]
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"finding missing required field(s): {', '.join(missing)}")

    finding = Finding(
        finding_id=str(raw["finding_id"]).strip(),
        severity=_coerce_enum(Severity, raw["severity"], "severity"),
        category=_coerce_enum(FindingCategory, raw["category"], "category"),
        message=str(raw["message"]).strip(),
        recommended_action=str(raw["recommended_action"]).strip(),
        acceptance_check=str(raw["acceptance_check"]).strip(),
        evidence_quote=str(raw.get("evidence_quote") or "").strip(),
    )
    validate_finding(finding)
    return finding


def validate_finding(finding: Finding) -> None:
    if not finding.finding_id:
        raise ValueError("finding_id must not be empty")
    if not finding.message:
        raise ValueError("finding.message must not be empty")
    if not finding.recommended_action:
        raise ValueError("finding.recommended_action must not be empty")
    if not finding.acceptance_check:
        raise ValueError("finding.acceptance_check must not be empty")


def result_from_dict(raw: dict[str, Any]) -> AdvisorResult:
    if not isinstance(raw, dict):
        raise ValueError("AdvisorResult must be a JSON object")

    findings_raw = raw.get("findings", [])
    if not isinstance(findings_raw, list):
        raise ValueError("findings must be a list")
    findings = tuple(finding_from_dict(item) for item in findings_raw)

    unresolved_raw = raw.get("known_unresolved", [])
    if not isinstance(unresolved_raw, list):
        raise ValueError("known_unresolved must be a list")

    diagnostics_raw = raw.get("diagnostics", [])
    if not isinstance(diagnostics_raw, list):
        raise ValueError("diagnostics must be a list")

    error_class = raw.get("error_class")
    result = AdvisorResult(
        phase=_coerce_enum(AdvisorPhase, raw.get("phase"), "phase"),
        verdict=_coerce_enum(AdvisorVerdict, raw.get("verdict"), "verdict"),
        findings=findings,
        known_unresolved=tuple(str(item).strip() for item in unresolved_raw if str(item).strip()),
        degraded=bool(raw.get("degraded", False)),
        error_class=str(error_class).strip() if error_class else None,
        diagnostics=tuple(str(item).strip() for item in diagnostics_raw if str(item).strip()),
        unavailable_reason=str(raw.get("unavailable_reason") or "").strip(),
        final_improvement=str(raw.get("final_improvement") or "").strip(),
    )
    validate_result(result)
    return result


def validate_result(result: AdvisorResult) -> None:
    for finding in result.findings:
        validate_finding(finding)
    if result.degraded and not result.findings and not result.known_unresolved:
        raise ValueError("degraded=true requires findings or known_unresolved")
    if result.error_class is not None and not result.error_class.strip():
        raise ValueError("error_class must be null or a non-empty string")
    if result.degraded and not (result.diagnostics or result.unavailable_reason):
        raise ValueError("degraded=true requires diagnostics or unavailable_reason")


def finding_to_dict(finding: Finding) -> dict[str, Any]:
    return {
        "finding_id": finding.finding_id,
        "severity": finding.severity.value,
        "category": finding.category.value,
        "message": finding.message,
        "recommended_action": finding.recommended_action,
        "acceptance_check": finding.acceptance_check,
        "evidence_quote": finding.evidence_quote,
    }


def result_to_dict(result: AdvisorResult) -> dict[str, Any]:
    validate_result(result)
    return {
        "phase": result.phase.value,
        "verdict": result.verdict.value,
        "findings": [finding_to_dict(item) for item in result.findings],
        "known_unresolved": list(result.known_unresolved),
        "degraded": result.degraded,
        "error_class": result.error_class,
        "diagnostics": list(result.diagnostics),
        "unavailable_reason": result.unavailable_reason,
        "final_improvement": result.final_improvement,
    }


def finding_resolution_from_dict(raw: dict[str, Any]) -> FindingResolution:
    required = ["finding_id", "status", "reason"]
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"finding resolution missing required field(s): {', '.join(missing)}")
    resolution = FindingResolution(
        finding_id=str(raw["finding_id"]).strip(),
        status=_coerce_enum(FindingResolutionStatus, raw["status"], "status"),
        reason=str(raw["reason"]).strip(),
        evidence=str(raw.get("evidence") or "").strip(),
    )
    validate_finding_resolution(resolution)
    return resolution


def validate_finding_resolution(resolution: FindingResolution) -> None:
    if not resolution.finding_id:
        raise ValueError("finding resolution finding_id must not be empty")
    if not resolution.reason:
        raise ValueError("finding resolution reason must not be empty")


def finding_resolution_to_dict(resolution: FindingResolution) -> dict[str, Any]:
    validate_finding_resolution(resolution)
    return {
        "finding_id": resolution.finding_id,
        "status": resolution.status.value,
        "reason": resolution.reason,
        "evidence": resolution.evidence,
    }


def resolution_gate_from_dict(raw: dict[str, Any]) -> ResolutionGate:
    if not isinstance(raw, dict):
        raise ValueError("ResolutionGate must be a JSON object")
    resolutions_raw = raw.get("resolutions", [])
    if not isinstance(resolutions_raw, list):
        raise ValueError("resolutions must be a list")
    open_raw = raw.get("open_findings", [])
    if not isinstance(open_raw, list):
        raise ValueError("open_findings must be a list")
    gate = ResolutionGate(
        commander_decision=_coerce_enum(
            ResolutionDecision,
            raw.get("commander_decision"),
            "commander_decision",
        ),
        reason=str(raw.get("reason") or "").strip(),
        open_findings=tuple(str(item).strip() for item in open_raw if str(item).strip()),
        resolutions=tuple(finding_resolution_from_dict(item) for item in resolutions_raw),
    )
    validate_resolution_gate(gate)
    return gate


def validate_resolution_gate(gate: ResolutionGate) -> None:
    if not gate.reason:
        raise ValueError("resolution gate reason must not be empty")
    for resolution in gate.resolutions:
        validate_finding_resolution(resolution)
    if gate.commander_decision is ResolutionDecision.CONTINUE and gate.open_findings:
        raise ValueError("commander_decision=continue requires open_findings to be empty")
    if gate.commander_decision is ResolutionDecision.REQUIRES_RESOLUTION and not gate.open_findings:
        raise ValueError("commander_decision=requires_resolution requires open_findings")


def resolution_gate_to_dict(gate: ResolutionGate) -> dict[str, Any]:
    validate_resolution_gate(gate)
    return {
        "commander_decision": gate.commander_decision.value,
        "reason": gate.reason,
        "open_findings": list(gate.open_findings),
        "resolutions": [finding_resolution_to_dict(item) for item in gate.resolutions],
    }


def final_payload_from_dict(raw: dict[str, Any]) -> FinalPayload:
    if not isinstance(raw, dict):
        raise ValueError("FinalPayload must be a JSON object")
    required = [
        "actions_taken",
        "tests_or_checks",
        "known_unresolved",
        "final_answer_draft",
        "flow_summary",
    ]
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"FinalPayload missing required field(s): {', '.join(missing)}")
    actions_raw = raw["actions_taken"]
    checks_raw = raw["tests_or_checks"]
    unresolved_raw = raw["known_unresolved"]
    if not isinstance(actions_raw, list):
        raise ValueError("actions_taken must be a list")
    if not isinstance(checks_raw, list):
        raise ValueError("tests_or_checks must be a list")
    if not isinstance(unresolved_raw, list):
        raise ValueError("known_unresolved must be a list")
    payload = FinalPayload(
        actions_taken=tuple(_coerce_object_list(actions_raw, "actions_taken")),
        tests_or_checks=tuple(_coerce_object_list(checks_raw, "tests_or_checks")),
        known_unresolved=tuple(str(item).strip() for item in unresolved_raw if str(item).strip()),
        final_answer_draft=str(raw["final_answer_draft"]).strip(),
        flow_summary=str(raw["flow_summary"]).strip(),
    )
    validate_final_payload(payload)
    return payload


def plan_payload_from_dict(raw: dict[str, Any]) -> PlanPayload:
    if not isinstance(raw, dict):
        raise ValueError("PlanPayload must be a JSON object")
    required = [
        "user_message",
        "commander_interpretation",
        "task_plan",
        "coverage_table",
        "risk_level",
    ]
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"PlanPayload missing required field(s): {', '.join(missing)}")

    task_plan_raw = raw["task_plan"]
    coverage_raw = raw["coverage_table"]
    if not isinstance(task_plan_raw, list):
        raise ValueError("task_plan must be a list")
    if not isinstance(coverage_raw, list):
        raise ValueError("coverage_table must be a list")

    constraints_raw = raw.get("constraints", [])
    evidence_raw = raw.get("source_evidence", [])
    unresolved_raw = raw.get("known_unresolved", [])
    if not isinstance(constraints_raw, list):
        raise ValueError("constraints must be a list")
    if not isinstance(evidence_raw, list):
        raise ValueError("source_evidence must be a list")
    if not isinstance(unresolved_raw, list):
        raise ValueError("known_unresolved must be a list")

    payload = PlanPayload(
        user_message=_required_string(raw, "user_message"),
        commander_interpretation=_required_string(raw, "commander_interpretation"),
        task_plan=tuple(_coerce_non_empty_object_list(task_plan_raw, "task_plan")),
        coverage_table=tuple(_coerce_non_empty_object_list(coverage_raw, "coverage_table")),
        risk_level=_required_string(raw, "risk_level"),
        constraints=_coerce_string_tuple(constraints_raw),
        source_evidence=tuple(_coerce_object_list(evidence_raw, "source_evidence")),
        known_unresolved=_coerce_string_tuple(unresolved_raw),
    )
    validate_plan_payload(payload)
    return payload


def delegation_payload_from_dict(raw: dict[str, Any]) -> DelegationPayload:
    if not isinstance(raw, dict):
        raise ValueError("DelegationPayload must be a JSON object")
    required = [
        "commander_plan",
        "worker_assignments",
        "empty_result_policy",
        "risk_level",
    ]
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"DelegationPayload missing required field(s): {', '.join(missing)}")

    assignments_raw = raw["worker_assignments"]
    if not isinstance(assignments_raw, list):
        raise ValueError("worker_assignments must be a list")
    if not assignments_raw:
        raise ValueError("worker_assignments must not be empty")

    unresolved_raw = raw.get("known_unresolved", [])
    if not isinstance(unresolved_raw, list):
        raise ValueError("known_unresolved must be a list")

    payload = DelegationPayload(
        commander_plan=_required_string(raw, "commander_plan"),
        worker_assignments=tuple(
            worker_assignment_from_dict(item, index)
            for index, item in enumerate(assignments_raw)
        ),
        empty_result_policy=_required_string(raw, "empty_result_policy"),
        risk_level=_required_string(raw, "risk_level"),
        handoff_expectations=str(raw.get("handoff_expectations") or "").strip(),
        known_unresolved=_coerce_string_tuple(unresolved_raw),
    )
    validate_delegation_payload(payload)
    return payload


def worker_assignment_from_dict(raw: Any, index: int) -> WorkerAssignment:
    if not isinstance(raw, dict):
        raise ValueError(f"worker_assignments[{index}] must be an object")
    required = ["worker_id", "child_role", "scope", "expected_evidence"]
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(
            f"worker_assignments[{index}] missing required field(s): {', '.join(missing)}"
        )
    evidence_raw = raw["expected_evidence"]
    if not isinstance(evidence_raw, list):
        raise ValueError(f"worker_assignments[{index}].expected_evidence must be a list")
    assignment = WorkerAssignment(
        worker_id=_required_string(raw, "worker_id"),
        child_role=_required_string(raw, "child_role"),
        scope=_required_string(raw, "scope"),
        expected_evidence=tuple(
            _coerce_non_empty_object_list(
                evidence_raw,
                f"worker_assignments[{index}].expected_evidence",
            )
        ),
    )
    validate_worker_assignment(assignment, index)
    return assignment


def _required_string(raw: dict[str, Any], field_name: str) -> str:
    if raw[field_name] is None:
        raise ValueError(f"{field_name} must not be empty")
    value = str(raw[field_name]).strip()
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    return value


def _coerce_object_list(raw: list[Any], field_name: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if isinstance(item, dict):
            objects.append(item)
            continue
        if isinstance(item, str) and item.strip():
            objects.append({"summary": item.strip()})
            continue
        raise ValueError(f"{field_name}[{index}] must be an object or non-empty string")
    return objects


def _coerce_non_empty_object_list(raw: list[Any], field_name: str) -> list[dict[str, Any]]:
    objects = _coerce_object_list(raw, field_name)
    if not objects:
        raise ValueError(f"{field_name} must not be empty")
    return objects


def _coerce_string_tuple(raw: list[Any]) -> tuple[str, ...]:
    return tuple(str(item).strip() for item in raw if str(item).strip())


def validate_plan_payload(payload: PlanPayload) -> None:
    if not payload.user_message:
        raise ValueError("user_message must not be empty")
    if not payload.commander_interpretation:
        raise ValueError("commander_interpretation must not be empty")
    if not payload.task_plan:
        raise ValueError("task_plan must not be empty")
    if not payload.coverage_table:
        raise ValueError("coverage_table must not be empty")
    if not payload.risk_level:
        raise ValueError("risk_level must not be empty")


def validate_worker_assignment(assignment: WorkerAssignment, index: int) -> None:
    if not assignment.worker_id:
        raise ValueError(f"worker_assignments[{index}].worker_id must not be empty")
    if not assignment.child_role:
        raise ValueError(f"worker_assignments[{index}].child_role must not be empty")
    if not assignment.scope:
        raise ValueError(f"worker_assignments[{index}].scope must not be empty")
    if not assignment.expected_evidence:
        raise ValueError(f"worker_assignments[{index}].expected_evidence must not be empty")


def validate_delegation_payload(payload: DelegationPayload) -> None:
    if not payload.commander_plan:
        raise ValueError("commander_plan must not be empty")
    if not payload.worker_assignments:
        raise ValueError("worker_assignments must not be empty")
    if not payload.empty_result_policy:
        raise ValueError("empty_result_policy must not be empty")
    if not payload.risk_level:
        raise ValueError("risk_level must not be empty")
    for index, assignment in enumerate(payload.worker_assignments):
        validate_worker_assignment(assignment, index)


def plan_payload_to_dict(payload: PlanPayload) -> dict[str, Any]:
    validate_plan_payload(payload)
    return {
        "user_message": payload.user_message,
        "commander_interpretation": payload.commander_interpretation,
        "task_plan": list(payload.task_plan),
        "coverage_table": list(payload.coverage_table),
        "risk_level": payload.risk_level,
        "constraints": list(payload.constraints),
        "source_evidence": list(payload.source_evidence),
        "known_unresolved": list(payload.known_unresolved),
    }


def worker_assignment_to_dict(assignment: WorkerAssignment) -> dict[str, Any]:
    validate_worker_assignment(assignment, 0)
    return {
        "worker_id": assignment.worker_id,
        "child_role": assignment.child_role,
        "scope": assignment.scope,
        "expected_evidence": list(assignment.expected_evidence),
    }


def delegation_payload_to_dict(payload: DelegationPayload) -> dict[str, Any]:
    validate_delegation_payload(payload)
    return {
        "commander_plan": payload.commander_plan,
        "worker_assignments": [
            worker_assignment_to_dict(assignment)
            for assignment in payload.worker_assignments
        ],
        "empty_result_policy": payload.empty_result_policy,
        "risk_level": payload.risk_level,
        "handoff_expectations": payload.handoff_expectations,
        "known_unresolved": list(payload.known_unresolved),
    }


def validate_final_payload(payload: FinalPayload) -> None:
    if not payload.final_answer_draft:
        raise ValueError("final_answer_draft must not be empty")
    if not payload.flow_summary:
        raise ValueError("flow_summary must not be empty")


def final_payload_to_dict(payload: FinalPayload) -> dict[str, Any]:
    validate_final_payload(payload)
    return {
        "actions_taken": list(payload.actions_taken),
        "tests_or_checks": list(payload.tests_or_checks),
        "known_unresolved": list(payload.known_unresolved),
        "final_answer_draft": payload.final_answer_draft,
        "flow_summary": payload.flow_summary,
    }


def advisor_result_json_schema() -> dict[str, Any]:
    """JSON Schema passed to Hermes ctx.llm.complete_structured."""

    return {
        "type": "object",
        "properties": {
            "phase": {"type": "string", "enum": [phase.value for phase in AdvisorPhase]},
            "verdict": {"type": "string", "enum": [verdict.value for verdict in AdvisorVerdict]},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "finding_id": {"type": "string"},
                        "severity": {"type": "string", "enum": [item.value for item in Severity]},
                        "category": {
                            "type": "string",
                            "enum": [item.value for item in FindingCategory],
                        },
                        "message": {"type": "string"},
                        "recommended_action": {"type": "string"},
                        "acceptance_check": {"type": "string"},
                        "evidence_quote": {"type": "string"},
                    },
                    "required": [
                        "finding_id",
                        "severity",
                        "category",
                        "message",
                        "recommended_action",
                        "acceptance_check",
                    ],
                },
            },
            "known_unresolved": {"type": "array", "items": {"type": "string"}},
            "degraded": {"type": "boolean"},
            "error_class": {"type": ["string", "null"]},
            "diagnostics": {"type": "array", "items": {"type": "string"}},
            "unavailable_reason": {"type": "string"},
            "final_improvement": {"type": "string"},
        },
        "required": [
            "phase",
            "verdict",
            "findings",
            "known_unresolved",
            "degraded",
            "error_class",
            "diagnostics",
            "unavailable_reason",
            "final_improvement",
        ],
    }
