import pytest
from advisor_gate.schemas import (
    AdvisorPhase,
    AdvisorVerdict,
    Finding,
    FindingCategory,
    FindingResolutionStatus,
    ResolutionDecision,
    Severity,
    delegation_payload_from_dict,
    final_payload_from_dict,
    plan_payload_from_dict,
    resolution_gate_from_dict,
    resolution_gate_to_dict,
    result_from_dict,
    result_to_dict,
)


def test_valid_advisor_result_roundtrip():
    result = result_from_dict(
        {
            "phase": "A3_FINAL",
            "verdict": "PASS",
            "findings": [],
            "known_unresolved": [],
            "degraded": False,
            "error_class": None,
            "diagnostics": [],
            "unavailable_reason": "",
            "final_improvement": "",
        }
    )

    assert result.phase is AdvisorPhase.A3_FINAL
    assert result.verdict is AdvisorVerdict.PASS
    assert result_to_dict(result)["phase"] == "A3_FINAL"


def test_invalid_verdict_rejected():
    with pytest.raises(ValueError, match="verdict"):
        result_from_dict(
            {
                "phase": "A3_FINAL",
                "verdict": "MAYBE",
                "findings": [],
                "known_unresolved": [],
                "degraded": False,
                "error_class": None,
                "diagnostics": [],
                "unavailable_reason": "",
                "final_improvement": "",
            }
        )


def test_degraded_without_findings_or_unresolved_rejected():
    with pytest.raises(ValueError, match="degraded=true"):
        result_from_dict(
            {
                "phase": "A3_EXCEPTION",
                "verdict": "CHANGES_REQUIRED",
                "findings": [],
                "known_unresolved": [],
                "degraded": True,
                "error_class": "TimeoutError",
                "diagnostics": [],
                "unavailable_reason": "",
                "final_improvement": "",
            }
        )


def test_finding_schema_accepts_required_shape():
    result = result_from_dict(
        {
            "phase": "A1_PLAN",
            "verdict": "CHANGES_REQUIRED",
            "findings": [
                {
                    "finding_id": "F-001",
                    "severity": "high",
                    "category": "evidence_gap",
                    "message": "Missing source evidence.",
                    "recommended_action": "Cite docs/source before implementation.",
                    "acceptance_check": "Plan includes concrete source references.",
                    "evidence_quote": "",
                }
            ],
            "known_unresolved": [],
            "degraded": False,
            "error_class": None,
            "diagnostics": [],
            "unavailable_reason": "",
            "final_improvement": "",
        }
    )

    finding = result.findings[0]
    assert isinstance(finding, Finding)
    assert finding.severity is Severity.HIGH
    assert finding.category is FindingCategory.EVIDENCE_GAP


def test_degraded_requires_diagnostics_or_unavailable_reason():
    with pytest.raises(ValueError, match="diagnostics"):
        result_from_dict(
            {
                "phase": "A3_EXCEPTION",
                "verdict": "CHANGES_REQUIRED",
                "findings": [
                    {
                        "finding_id": "F-001",
                        "severity": "medium",
                        "category": "exception",
                        "message": "Advisor unavailable.",
                        "recommended_action": "Retry.",
                        "acceptance_check": "Advisor returns valid JSON.",
                    }
                ],
                "known_unresolved": [],
                "degraded": True,
                "error_class": "TimeoutError",
                "diagnostics": [],
                "unavailable_reason": "",
                "final_improvement": "",
            }
        )


def test_resolution_gate_roundtrip_continue_requires_no_open_findings():
    gate = resolution_gate_from_dict(
        {
            "commander_decision": "continue",
            "reason": "All findings are resolved.",
            "open_findings": [],
            "resolutions": [
                {
                    "finding_id": "F-001",
                    "status": "resolved",
                    "reason": "Added verification evidence.",
                    "evidence": "pytest passed",
                }
            ],
        }
    )

    assert gate.commander_decision is ResolutionDecision.CONTINUE
    assert gate.resolutions[0].status is FindingResolutionStatus.RESOLVED
    assert resolution_gate_to_dict(gate)["commander_decision"] == "continue"


def test_resolution_gate_continue_rejects_open_findings():
    with pytest.raises(ValueError, match="open_findings"):
        resolution_gate_from_dict(
            {
                "commander_decision": "continue",
                "reason": "Still open.",
                "open_findings": ["F-001"],
                "resolutions": [],
            }
        )


def test_final_payload_requires_source_image_shape():
    payload = final_payload_from_dict(
        {
            "actions_taken": [{"item_id": "A-1", "summary": "Implemented gate."}],
            "tests_or_checks": ["python -m pytest"],
            "known_unresolved": [],
            "final_answer_draft": "Done.",
            "flow_summary": "Plan -> audit -> final.",
        }
    )

    assert payload.actions_taken[0]["item_id"] == "A-1"
    assert payload.tests_or_checks[0]["summary"] == "python -m pytest"


def test_plan_payload_requires_source_image_shape():
    payload = plan_payload_from_dict(
        {
            "user_message": "Implement the gate.",
            "commander_interpretation": "Use plugin changes only.",
            "task_plan": ["inspect", {"step": "implement"}],
            "coverage_table": [{"requirement": "A1", "coverage": "schema test"}],
            "risk_level": "medium",
            "constraints": ["No Hermes core patch."],
            "source_evidence": ["docs"],
            "known_unresolved": [],
        }
    )

    assert payload.user_message == "Implement the gate."
    assert payload.task_plan[0]["summary"] == "inspect"


def test_delegation_payload_requires_worker_role_scope_and_evidence():
    payload = delegation_payload_from_dict(
        {
            "commander_plan": "Delegate focused verification.",
            "worker_assignments": [
                {
                    "worker_id": "worker-1",
                    "child_role": "leaf",
                    "scope": "Run focused checks.",
                    "expected_evidence": ["pytest result"],
                }
            ],
            "empty_result_policy": "Mark empty output unresolved.",
            "risk_level": "medium",
        }
    )

    assert payload.worker_assignments[0].child_role == "leaf"
    assert payload.worker_assignments[0].expected_evidence[0]["summary"] == "pytest result"


def test_delegation_payload_rejects_empty_worker_assignments():
    with pytest.raises(ValueError, match="worker_assignments"):
        delegation_payload_from_dict(
            {
                "commander_plan": "Delegate focused verification.",
                "worker_assignments": [],
                "empty_result_policy": "Mark empty output unresolved.",
                "risk_level": "medium",
            }
        )
