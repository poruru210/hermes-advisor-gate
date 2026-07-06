# End-to-End Validation Runbook

This runbook validates the Advisor overlay without patching Hermes core.

The validation defines roles at the scenario level:

| Scenario role | Hermes-backed evidence | Advisor responsibility |
|---|---|---|
| User | The validation request in the A1 packet | Source request to compare against the plan |
| Commander | Parent `session_id` and the caller of Advisor tools | Plan, delegation, exception handling, final decision |
| Worker | Child `session_id` plus `child_role` from Hermes subagent hooks | Narrow execution result and evidence |
| Advisor | `advisor_audit` and `advisor_resolution_gate` | Review-only audit, findings, verdicts, receipts |
| Receipt | Advisor JSONL records | Evidence that the flow ran in order |

Responsibility boundaries:

- The User states the desired outcome in natural language.
- The Commander decides whether delegation is useful.
- If the Commander creates an `orchestrator` child, that child is a Worker from
  the parent perspective and a local Commander for its own children.
- Leaf Workers perform narrow evidence-producing tasks and do not delegate
  further.
- Advisor audits the plan, delegation packet, evidence, exception handling, and
  final claim. Advisor does not choose the decomposition, worker count, or
  Worker assignments.

## Scope

This validates the plugin and skill design through official Hermes plugin
surfaces:

- `advisor_audit`
- `advisor_resolution_gate`
- `pre_tool_call`
- `post_tool_call`
- `subagent_start`
- `subagent_stop`
- `pre_verify` / final delivery gate behavior

It does not validate Hermes standard session-history integration. That remains
outside the plugin-only scope.

## Deterministic Plugin Flow

Run this in the repository checkout:

```bash
mise run check
```

For the focused end-to-end scenario:

```bash
uv run --extra dev python -m pytest tests/test_end_to_end_flow.py
```

Expected result:

```text
tests/test_end_to_end_flow.py .  [100%]
```

The focused test proves this sequence:

1. A mutating action is blocked before `A1_PLAN`.
2. `A1_PLAN` passes with user request, Commander interpretation, plan,
   coverage table, risk level, constraints, and evidence.
3. The mutating action is allowed after same-turn `A1_PLAN`.
4. Delegation is blocked before `A2_DELEGATION`.
5. `A2_DELEGATION` passes with Commander plan, Worker assignment,
   `child_role`, Worker scope, expected evidence, empty-result policy, and risk
   level.
6. Delegation is allowed after same-turn `A2_DELEGATION`.
7. A Worker child session start is recorded.
8. Final delivery is deferred while the Worker is active.
9. A Worker child session stop is recorded.
10. A planned tool failure is recorded.
11. Final delivery requests `A3_EXCEPTION`.
12. `A3_EXCEPTION` passes.
13. Final delivery requests `A3_FINAL`.
14. `A3_FINAL` receives observed Worker role evidence from receipts.
15. Final delivery requests `advisor_resolution_gate`.
16. `advisor_resolution_gate` records Commander continuation.
17. Final delivery is allowed.

The focused test uses one leaf Worker so the receipt path is deterministic. It
does not assert that production turns must delegate, use an orchestrator, or
create a fixed number of leaf Workers.

## Pi Validation

On the Pi host, update the repository checkout:

```bash
cd /home/pi/hermes-runtime
git pull --ff-only
mise run check
uv run --extra dev python -m pytest tests/test_end_to_end_flow.py
```

Refresh the installed plugin through the official Hermes installer:

```bash
hermes plugins install poruru210/hermes-runtime/plugin/advisor-gate --force --enable
hermes gateway restart
hermes config check
hermes doctor
hermes plugins list --plain --no-bundled
hermes tools list
```

Expected signs:

```text
advisor-gate: enabled
Tool Availability: advisor_gate
```

Do not commit live receipt files, Hermes logs, tokens, or local terminal logs.
Record only sanitized command outcomes in documentation or final reports.

## Live Commander / Worker Smoke

Use a new Hermes conversation after the plugin is installed and enabled.

User-facing prompt:

```text
Please check whether this repository's Advisor Gate is wired correctly for
planning, delegation, worker evidence, exception handling, final audit, and
resolution recording. Use read-only inspection where possible, split the work
only if it is useful, and include concrete evidence before finalizing.
```

The user prompt intentionally does not assign Commander, Worker, Level 1, or
Level 2 roles. Those are implementation roles inferred from Hermes' parent
session, child session, and `child_role` evidence.

Expected Commander behavior:

- Run `advisor_audit` for `A1_PLAN` before implementation or mutating actions.
- Decide whether delegation is useful.
- If delegating, run `advisor_audit` for `A2_DELEGATION` before delegation.
- Choose the number and scope of Workers from the task, not from a fixed
  topology rule.
- Keep Worker scope narrow and evidence-focused.
- Include Worker evidence and observed receipts in `A3_FINAL`.
- Record `advisor_resolution_gate` before final delivery.
- If any Advisor result is `CHANGES_REQUIRED` or `BLOCK`, resolve or report it
  instead of finalizing.

Expected evidence:

- One parent Commander session id.
- `A1_PLAN`, `A3_FINAL`, and `RESOLUTION_GATE` receipts.
- If delegation is used, one or more Worker child session ids.
- If delegation is used, `child_role` recorded for each Worker.
- If delegation is used, an `A2_DELEGATION` receipt before delegation.
- If any tool failure occurs, an `A3_EXCEPTION` receipt after that failure.
- Final answer does not include hidden unresolved Advisor findings.

## Pass / Fail Criteria

Pass only when all of these are true:

- No Hermes core files are changed.
- Plugin checks pass locally and on Pi.
- The focused end-to-end test passes on Pi.
- Hermes reports `advisor-gate` enabled and `advisor_gate` available.
- Receipts show the Commander/Worker/Advisor sequence in order.
- Final delivery is blocked until current `A3_FINAL` and resolution gate exist.

Fail or unresolved when any of these are true:

- `child_role` is missing from Worker evidence.
- A final draft can pass without current `A3_FINAL`.
- A passed `A3_FINAL` can finish without `advisor_resolution_gate` when
  resolution gate is required.
- A tool failure after the latest exception audit can finish without a later
  `A3_EXCEPTION`.
- Verification depends on local logs or secrets that cannot be shared.
