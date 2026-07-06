from advisor_gate.packets import (
    build_advisor_structured_input,
    build_delegation_packet,
    build_final_packet,
    build_plan_packet,
    build_prompt_packet,
)


def test_prompt_packet_includes_phase_and_payload():
    packet = build_prompt_packet("A1_PLAN", {"task": "do it"})
    assert packet["phase"] == "A1_PLAN"
    assert packet["payload"]["task"] == "do it"
    assert packet["required_output"] == "AdvisorResult JSON object"


def test_structured_input_mentions_phase():
    instructions, input_blocks = build_advisor_structured_input("A3_FINAL", {"final": "done"})
    assert "A3_FINAL" in instructions
    assert input_blocks[0]["type"] == "text"
    assert "final" in input_blocks[0]["text"]


def test_plan_packet_has_required_payload_fields():
    packet = build_plan_packet(
        user_message="task",
        commander_interpretation="plan",
        task_plan=["inspect"],
        coverage_table=[{"requirement": "A1", "coverage": "test"}],
        risk_level="low",
        constraints=["constraint"],
        source_evidence=["evidence"],
    )

    assert set(packet) == {
        "user_message",
        "commander_interpretation",
        "task_plan",
        "coverage_table",
        "risk_level",
        "constraints",
        "source_evidence",
        "known_unresolved",
    }
    assert packet["task_plan"][0]["summary"] == "inspect"


def test_delegation_packet_has_required_payload_fields():
    packet = build_delegation_packet(
        commander_plan="delegate focused work",
        worker_assignments=[
            {
                "worker_id": "worker-1",
                "child_role": "leaf",
                "scope": "Run focused checks.",
                "expected_evidence": ["pytest"],
            }
        ],
        empty_result_policy="Mark empty output unresolved.",
        risk_level="medium",
    )

    assert set(packet) == {
        "commander_plan",
        "worker_assignments",
        "empty_result_policy",
        "risk_level",
        "handoff_expectations",
        "known_unresolved",
    }
    assert packet["worker_assignments"][0]["child_role"] == "leaf"


def test_build_final_packet_has_source_image_payload_shape():
    packet = build_final_packet(
        actions_taken=["implemented"],
        tests_or_checks=[{"command": "pytest", "status": "passed"}],
        known_unresolved=[],
        final_answer_draft="Done.",
        flow_summary="Plan -> Final.",
    )

    assert set(packet) == {
        "actions_taken",
        "tests_or_checks",
        "known_unresolved",
        "final_answer_draft",
        "flow_summary",
    }
    assert packet["actions_taken"][0]["summary"] == "implemented"
