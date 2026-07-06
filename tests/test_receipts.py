from advisor_gate.schemas import (
    AdvisorPhase,
    AdvisorResult,
    AdvisorVerdict,
    resolution_gate_from_dict,
)
from advisor_gate.store import ReceiptStore, redact_secrets


def test_jsonl_write_read_roundtrip(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    result = AdvisorResult(phase=AdvisorPhase.A3_FINAL, verdict=AdvisorVerdict.PASS)

    store.append_result(session_id="s1", result=result, source="test")

    entries = store.read_all()
    assert len(entries) == 1
    assert entries[0]["session_id"] == "s1"
    assert entries[0]["verdict"] == "PASS"
    assert store.latest_result(session_id="s1").verdict is AdvisorVerdict.PASS


def test_redacts_secret_like_keys():
    data = redact_secrets(
        {
            "api_key": "abc",
            "nested": {"token_value": "secret"},
            "safe": "visible",
        }
    )

    assert data["api_key"] == "[REDACTED]"
    assert data["nested"]["token_value"] == "[REDACTED]"
    assert data["safe"] == "visible"


def test_resolution_gate_write_read_roundtrip(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    gate = resolution_gate_from_dict(
        {
            "commander_decision": "continue",
            "reason": "No open findings.",
            "open_findings": [],
            "resolutions": [],
        }
    )

    store.append_resolution_gate(session_id="s1", gate=gate, source="test")

    assert store.latest_resolution_gate(session_id="s1").commander_decision.value == "continue"


def test_subagent_role_summary_returns_parent_child_role_evidence(tmp_path):
    store = ReceiptStore.from_path(tmp_path / "receipts.jsonl")
    store.append(
        {
            "timestamp": "2026-07-06T00:00:00+00:00",
            "source": "subagent_start",
            "session_id": "parent",
            "event": "subagent_start",
            "extra": {
                "parent_session_id": "parent",
                "child_session_id": "child",
                "child_role": "leaf",
            },
        }
    )

    summary = store.subagent_role_summary("parent")

    assert summary[0]["parent_session_id"] == "parent"
    assert summary[0]["child_session_id"] == "child"
    assert summary[0]["child_role"] == "leaf"
