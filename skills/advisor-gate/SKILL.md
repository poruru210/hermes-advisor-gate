# Advisor Gate

Use this skill when work must pass Hermes Advisor Gate before final delivery.

The Advisor is review-only. It must not execute tools, edit files, deploy,
or claim implementation work. Use the `advisor_audit` tool to audit packets.
Use `advisor_resolution_gate` to record the Commander's decision about Advisor
findings after A3-Final.

Run audits at these points:

- `A1_PLAN`: before implementation, with task, plan, constraints, and evidence.
- `A2_DELEGATION`: after delegation planning or subagent fanout decisions.
- `A3_EXCEPTION`: after tool, model, runtime, or subagent failures.
- `A3_FINAL`: before final response, with final draft, verification evidence,
  known unresolved items, receipts, and changed files.

For `A1_PLAN`, the packet must have this shape:

- `user_message`: the original user request or a faithful summary.
- `commander_interpretation`: how the Commander interprets the task, scope, and
  source of truth.
- `task_plan`: list of planned steps as objects or non-empty strings.
- `coverage_table`: list mapping requirements to planned coverage as objects or
  non-empty strings.
- `risk_level`: concise risk label such as `low`, `medium`, or `high`.
- `constraints`: optional list of constraints.
- `source_evidence`: optional list of source references or verification inputs.
- `known_unresolved`: optional list of unresolved items.

Example:

```json
{
  "phase": "A1_PLAN",
  "packet": {
    "user_message": "Implement Advisor Gate changes.",
    "commander_interpretation": "Use only plugin and skill changes; do not patch Hermes core.",
    "task_plan": [
      {"step": "Validate A1 and A2 packets before LLM audit."},
      {"step": "Add role evidence to A2 and A3 audit packets."}
    ],
    "coverage_table": [
      {"requirement": "A1 input validation", "planned_coverage": "schema and handler tests"},
      {"requirement": "child_role use", "planned_coverage": "receipt summary in audit packet"}
    ],
    "risk_level": "medium",
    "constraints": ["No Hermes core modification."],
    "source_evidence": [{"source": "official Hermes hook context"}],
    "known_unresolved": []
  }
}
```

For `A2_DELEGATION`, the packet must have this shape:

- `commander_plan`: the parent/Commander plan that justifies delegation.
- `worker_assignments`: non-empty list. Each item must include `worker_id`,
  `child_role`, `scope`, and `expected_evidence`.
- `empty_result_policy`: what the Commander will do if a worker returns no useful
  result or exceeds scope.
- `risk_level`: concise risk label.
- `handoff_expectations`: optional expectations for exception and final handoff.
- `known_unresolved`: optional list of unresolved items.

Use the exact `child_role` value supplied by Hermes hook context when it is
known. If delegation has not started yet, state the intended child role and make
the scope narrow enough for Advisor to audit.

Example:

```json
{
  "phase": "A2_DELEGATION",
  "packet": {
    "commander_plan": "Delegate independent verification of receipt behavior.",
    "worker_assignments": [
      {
        "worker_id": "verification-worker",
        "child_role": "leaf",
        "scope": "Inspect receipt records and run focused tests only.",
        "expected_evidence": [
          {"type": "test", "description": "Receipt summary test result"},
          {"type": "source", "description": "Relevant hook or store code"}
        ]
      }
    ],
    "empty_result_policy": "Treat empty or over-broad output as unresolved and re-scope.",
    "risk_level": "medium",
    "handoff_expectations": "Worker findings must be reflected in A3_FINAL.",
    "known_unresolved": []
  }
}
```

For `A3_FINAL`, the packet must have this shape:

- `actions_taken`: list of evidence objects or summaries.
- `tests_or_checks`: list of command/test/log/check evidence objects or summaries.
- `known_unresolved`: list of unresolved items, also reflected in the final draft.
- `final_answer_draft`: the exact final answer draft to be audited.
- `flow_summary`: concise Plan/Delegation/Exception/Final flow summary.

When subagents were used, include worker evidence in `actions_taken` or
`tests_or_checks`. The plugin also adds observed child session records to A2/A3
audit packets when Hermes provides parent/child hook data.

Treat verdicts as follows:

- `PASS`: continue.
- `CHANGES_REQUIRED`: resolve findings or document unresolved items before final.
- `BLOCK`: stop until the blocking finding is resolved.

The plugin enforces A1/A2 before action:

- Configured mutating, executing, or dispatching tools are blocked until
  `A1_PLAN` passes for the current turn.
- `delegate_task` is blocked until both `A1_PLAN` and `A2_DELEGATION` pass for
  the current turn.
- If a tool/runtime failure is observed, final delivery is blocked until a
  later `A3_EXCEPTION` audit passes.
- `A3_FINAL` must be run after the latest relevant tool, subagent, or exception
  event; stale final audits are not accepted.
- If blocked, run the requested `advisor_audit` phase, address any findings,
  and retry the action only after the Advisor policy action is `continue`.

Before final delivery, call `advisor_resolution_gate`:

- Use `commander_decision="continue"` only when no open findings remain.
- Use `commander_decision="requires_resolution"` when findings remain open.
- Every Advisor finding must be marked `accepted`, `resolved`, `deferred`, or
  `rejected` with a reason and evidence.
- Do not hide unresolved or deferred findings; include them in `known_unresolved`
  and in the final answer.

Do not hide degraded Advisor behavior. If the audit cannot run or returns
invalid JSON, keep the degraded receipt and report it honestly.
