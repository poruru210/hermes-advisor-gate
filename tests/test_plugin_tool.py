import json
from types import SimpleNamespace

from advisor_gate.audit_handlers import advisor_audit_handler
from advisor_gate.config import AdvisorGateConfig
from advisor_gate.event_hooks import on_subagent_start
from advisor_gate.pre_tool_gate import on_pre_tool_call
from advisor_gate.resolution_handlers import advisor_resolution_gate_handler
from advisor_gate.store import ReceiptStore


class FakeLlm:
    def __init__(self, parsed):
        self.parsed = parsed
        self.calls = []

    def complete_structured(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(parsed=self.parsed, text=json.dumps(self.parsed))


def _valid_plan_packet():
    return {
        "user_message": "check",
        "commander_interpretation": "Review the requested task before work.",
        "task_plan": [{"step": "Inspect current behavior."}],
        "coverage_table": [{"requirement": "plan audit", "coverage": "unit test"}],
        "risk_level": "low",
    }


def _valid_delegation_packet():
    return {
        "commander_plan": "Delegate a focused verification task.",
        "worker_assignments": [
            {
                "worker_id": "worker-1",
                "child_role": "leaf",
                "scope": "Run focused verification only.",
                "expected_evidence": [{"type": "test", "description": "pytest result"}],
            }
        ],
        "empty_result_policy": "Treat empty output as unresolved.",
        "risk_level": "medium",
    }


def _valid_final_packet():
    return {
        "actions_taken": [{"summary": "implemented"}],
        "tests_or_checks": [{"command": "pytest", "status": "passed"}],
        "known_unresolved": [],
        "final_answer_draft": "Done.",
        "flow_summary": "Plan -> Final.",
    }


def test_advisor_audit_tool_returns_result_and_writes_receipt(tmp_path):
    parsed = {
        "phase": "A1_PLAN",
        "verdict": "PASS",
        "findings": [],
        "known_unresolved": [],
        "degraded": False,
        "error_class": None,
    }
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    llm = FakeLlm(parsed)

    raw = advisor_audit_handler(
        {"phase": "A1_PLAN", "packet": _valid_plan_packet(), "session_id": "s1"},
        llm=llm,
        store=store,
        config=AdvisorGateConfig(),
    )

    result = json.loads(raw)
    assert result["verdict"] == "PASS"
    assert result["policy_action"] == "continue"
    assert store.read_all()[0]["session_id"] == "s1"
    assert llm.calls[0]["schema_name"] == "AdvisorResult"


def test_advisor_audit_receipt_uses_pre_tool_call_context(tmp_path):
    parsed = {
        "phase": "A1_PLAN",
        "verdict": "PASS",
        "findings": [],
        "known_unresolved": [],
        "degraded": False,
        "error_class": None,
    }
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    on_pre_tool_call(
        store,
        AdvisorGateConfig(),
        tool_name="advisor_audit",
        session_id="s1",
        task_id="task-1",
        args={"phase": "A1_PLAN", "packet": _valid_plan_packet()},
        turn_id="turn-1",
        tool_call_id="call-1",
        api_request_id="api-1",
    )

    advisor_audit_handler(
        {"phase": "A1_PLAN", "packet": _valid_plan_packet(), "session_id": "s1"},
        llm=FakeLlm(parsed),
        store=store,
        config=AdvisorGateConfig(),
    )

    receipt = store.read_all()[-1]
    context = receipt["extra"]["call_context"]
    assert context["turn_id"] == "turn-1"
    assert context["tool_call_id"] == "call-1"
    assert context["api_request_id"] == "api-1"


def test_a3_final_requires_final_payload_shape(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    llm = FakeLlm(
        {
            "phase": "A3_FINAL",
            "verdict": "PASS",
            "findings": [],
            "known_unresolved": [],
            "degraded": False,
            "error_class": None,
        }
    )

    raw = advisor_audit_handler(
        {"phase": "A3_FINAL", "packet": {"final": "done"}, "session_id": "s-final"},
        llm=llm,
        store=store,
        config=AdvisorGateConfig(),
    )

    result = json.loads(raw)
    assert result["verdict"] == "CHANGES_REQUIRED"
    assert result["degraded"] is True
    assert "FinalPayload" in result["findings"][0]["message"]
    assert llm.calls == []


def test_a1_plan_requires_plan_payload_shape(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    llm = FakeLlm(
        {
            "phase": "A1_PLAN",
            "verdict": "PASS",
            "findings": [],
            "known_unresolved": [],
            "degraded": False,
            "error_class": None,
        }
    )

    raw = advisor_audit_handler(
        {"phase": "A1_PLAN", "packet": {"task": "too loose"}, "session_id": "s-plan"},
        llm=llm,
        store=store,
        config=AdvisorGateConfig(),
    )

    result = json.loads(raw)
    assert result["verdict"] == "CHANGES_REQUIRED"
    assert result["degraded"] is True
    assert "PlanPayload" in result["findings"][0]["message"]
    assert llm.calls == []


def test_a2_delegation_requires_worker_role_and_scope(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    llm = FakeLlm(
        {
            "phase": "A2_DELEGATION",
            "verdict": "PASS",
            "findings": [],
            "known_unresolved": [],
            "degraded": False,
            "error_class": None,
        }
    )

    packet = _valid_delegation_packet()
    del packet["worker_assignments"][0]["child_role"]
    raw = advisor_audit_handler(
        {"phase": "A2_DELEGATION", "packet": packet, "session_id": "s-delegation"},
        llm=llm,
        store=store,
        config=AdvisorGateConfig(),
    )

    result = json.loads(raw)
    assert result["verdict"] == "CHANGES_REQUIRED"
    assert result["degraded"] is True
    assert "child_role" in result["findings"][0]["message"]
    assert llm.calls == []


def test_a3_final_includes_observed_subagent_roles(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    on_subagent_start(
        store,
        parent_session_id="parent",
        child_session_id="child-1",
        child_role="leaf",
    )
    llm = FakeLlm(
        {
            "phase": "A3_FINAL",
            "verdict": "PASS",
            "findings": [],
            "known_unresolved": [],
            "degraded": False,
            "error_class": None,
        }
    )

    advisor_audit_handler(
        {"phase": "A3_FINAL", "packet": _valid_final_packet(), "session_id": "parent"},
        llm=llm,
        store=store,
        config=AdvisorGateConfig(),
    )

    prompt_packet = json.loads(llm.calls[0]["input"][0]["text"])
    observed = prompt_packet["payload"]["observed_subagents"]
    assert observed[0]["child_session_id"] == "child-1"
    assert observed[0]["child_role"] == "leaf"
    receipt_packet = store.read_all()[-1]["extra"]["packet"]
    assert receipt_packet["observed_subagents"][0]["child_role"] == "leaf"


def test_resolution_gate_tool_returns_result_and_writes_receipt(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")

    raw = advisor_resolution_gate_handler(
        {
            "commander_decision": "continue",
            "reason": "All findings resolved.",
            "open_findings": [],
            "resolutions": [
                {
                    "finding_id": "F-001",
                    "status": "resolved",
                    "reason": "Added test evidence.",
                    "evidence": "pytest passed",
                }
            ],
            "session_id": "s-gate",
        },
        store=store,
        config=AdvisorGateConfig(),
    )

    result = json.loads(raw)
    assert result["commander_decision"] == "continue"
    assert result["policy_action"] == "continue"
    assert store.latest_resolution_gate(session_id="s-gate").reason == "All findings resolved."


def test_invalid_llm_result_degrades_to_changes_required(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    llm = FakeLlm({"phase": "A3_FINAL", "verdict": "NOT_VALID"})

    raw = advisor_audit_handler(
        {"phase": "A3_FINAL", "packet": _valid_final_packet(), "session_id": "s2"},
        llm=llm,
        store=store,
        config=AdvisorGateConfig(),
    )

    result = json.loads(raw)
    assert result["verdict"] == "CHANGES_REQUIRED"
    assert result["degraded"] is True
    assert result["error_class"] == "ValueError"


def test_invalid_phase_degrades_without_raising(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    llm = FakeLlm({"phase": "A3_FINAL", "verdict": "PASS", "findings": []})

    raw = advisor_audit_handler(
        {"phase": "NOT_A_PHASE", "packet": {"final": "done"}, "session_id": "s3"},
        llm=llm,
        store=store,
        config=AdvisorGateConfig(),
    )

    result = json.loads(raw)
    assert result["phase"] == "A3_EXCEPTION"
    assert result["verdict"] == "CHANGES_REQUIRED"
    assert result["degraded"] is True
    assert result["error_class"] == "ValueError"


def test_packet_size_limit_degrades_before_llm_call(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    llm = FakeLlm({"phase": "A3_FINAL", "verdict": "PASS", "findings": []})

    raw = advisor_audit_handler(
        {
            "phase": "A3_FINAL",
            "packet": {
                "actions_taken": [],
                "tests_or_checks": [],
                "known_unresolved": [],
                "final_answer_draft": "x" * 100,
                "flow_summary": "size-limit test",
            },
            "session_id": "s4",
        },
        llm=llm,
        store=store,
        config=AdvisorGateConfig(max_input_chars=10),
    )

    result = json.loads(raw)
    assert result["verdict"] == "CHANGES_REQUIRED"
    assert result["degraded"] is True
    assert "max_input_chars" in result["findings"][0]["message"]
    assert llm.calls == []
