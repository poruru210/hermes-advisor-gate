---
name: advisor-flow
description: Run the Hermes Advisor Gate workflow. Use when Kanban-centered work must pass A1 plan, A2 assignment, A3 exception, A3 final, and resolution recording before final delivery while keeping Advisor review-only.
---

# Advisor Flow Runtime

Use this skill when work must pass Hermes Advisor Gate before final delivery.

The Advisor is review-only. It must not execute tools, edit files, deploy,
or claim implementation work. Use the `advisor_audit` tool to audit packets.
Use `advisor_resolution_gate` to record the Commander's decision about Advisor
findings after A3-Final.

Run audits at these points:

- `A1_PLAN`: before implementation, with task, plan, constraints, and evidence.
- `A2_DELEGATION`: after Kanban task assignment planning, before creating,
  linking, or unblocking work.
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

- `commander_plan`: the Commander plan that justifies Kanban assignment.
- `worker_assignments`: non-empty list. Each item must include `worker_id`,
  `child_role`, `scope`, and `expected_evidence`.
- `empty_result_policy`: what the Commander will do if a worker returns no useful
  result or exceeds scope.
- `risk_level`: concise risk label.
- `handoff_expectations`: optional expectations for exception and final handoff.
- `known_unresolved`: optional list of unresolved items.

For Kanban assignments, use `child_role="kanban_worker"` unless a narrower local
role is intentionally defined. Add these fields when known:

- `kanban_task_id`
- `parent_task_id`
- `assignee`
- `dependencies`
- `completion_contract`

Make the scope narrow enough for Advisor to audit before any `kanban_create`,
`kanban_link`, or `kanban_unblock` call.

Example:

```json
{
  "phase": "A2_DELEGATION",
  "packet": {
    "commander_plan": "Create a Kanban task for independent verification of receipt behavior.",
    "worker_assignments": [
      {
        "worker_id": "verification-worker",
        "child_role": "kanban_worker",
        "kanban_task_id": "planned-verification-task",
        "parent_task_id": "root-task-id",
        "assignee": "default",
        "dependencies": [],
        "scope": "Inspect receipt records and run focused tests only.",
        "expected_evidence": [
          {"type": "test", "description": "Receipt summary test result"},
          {"type": "source", "description": "Relevant hook or store code"}
        ],
        "completion_contract": "Finish with kanban_complete(summary, metadata) or kanban_block(reason)."
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

`final_answer_draft` is binding. After `A3_FINAL` passes and the resolution
gate permits continuation, the final answer must be the same text. Any extra
heading, rewritten sentence, omitted limitation, or added status line makes the
receipt stale and requires a new `A3_FINAL` audit.

When subagents were used, include worker evidence in `actions_taken` or
`tests_or_checks`. The plugin also adds observed child session records to A2/A3
audit packets when Hermes provides parent/child hook data.

When Kanban was used, include Kanban task ids, completion summaries, completion
metadata, comments, and unresolved blocked tasks in `actions_taken` or
`tests_or_checks`.

Treat verdicts as follows:

- `PASS`: continue.
- `CHANGES_REQUIRED`: resolve findings or document unresolved items before final.
- `BLOCK`: stop until the blocking finding is resolved.

The plugin enforces A1/A2 before action:

- Configured mutating, executing, or dispatching tools are blocked until
  `A1_PLAN` passes for the current turn.
- Configured assignment tools such as `kanban_create`, `kanban_link`,
  `kanban_unblock`, and compatibility `delegate_task` are blocked until both
  `A1_PLAN` and `A2_DELEGATION` pass for the current turn.
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
- Return the audited final draft verbatim after the resolution gate permits
  continuation. If you need to edit the final answer, rerun `A3_FINAL` first.

Record Advisor results on Kanban:

- For `PASS`, the Commander should write a concise `kanban_comment` on the
  parent task.
- For `CHANGES_REQUIRED`, the Commander should comment the findings and create
  or reopen Kanban work needed to resolve them.
- For `BLOCK`, the Commander should block the relevant task with the unresolved
  condition and stop final delivery.

Do not hide degraded Advisor behavior. If the audit cannot run or returns
invalid JSON, keep the degraded receipt and report it honestly.
