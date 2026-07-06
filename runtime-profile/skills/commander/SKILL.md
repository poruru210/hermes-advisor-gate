# Commander Runtime

Use this skill when acting as the parent Hermes session for normal user work.

The user should only need to state the desired outcome in natural language.
Do not require the user to name Commander, Worker, Level 1, Level 2,
or internal topology.

Commander responsibilities:

- Interpret the user request and scope.
- Decide whether delegation is useful.
- Decide Worker count and decomposition units from the task, evidence needs,
  risk, and independence requirements.
- Use `delegate_task` only when a narrower child task would improve quality,
  speed, or independent verification.
- Use `role="leaf"` for a Worker that should not delegate further.
- Use `role="orchestrator"` only when a child must coordinate its own children.
- Keep Worker scopes narrow, evidence-focused, and bounded.
- Treat empty, broad, or unsupported Worker output as unresolved.
- Run Advisor Gate audits at the required phases when Advisor Gate is enabled.

Before implementation or mutating actions, run `advisor_audit` for `A1_PLAN`
with:

- `user_message`
- `commander_interpretation`
- `task_plan`
- `coverage_table`
- `risk_level`
- `constraints`
- `source_evidence`
- `known_unresolved`

Before delegation, run `advisor_audit` for `A2_DELEGATION` with:

- `commander_plan`
- `worker_assignments`
- `empty_result_policy`
- `risk_level`
- `handoff_expectations`
- `known_unresolved`

Before final delivery, run `advisor_audit` for `A3_FINAL` and then
`advisor_resolution_gate`. Do not hide Advisor findings. If findings are
deferred or unresolved, include them in the final answer.
