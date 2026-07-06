# Integration Validation

## Local Checks Run

```bash
mise run check
```

Result:

```text
compile: success
pytest: 64 passed
ruff: success
ty: success
```

The standard local validation uses mise-managed Python and uv-managed
dependencies. It verifies:

- Python source compiles.
- Unit tests pass.
- Ruff lint passes.
- ty type checking passes for `plugin/advisor-gate/advisor_gate`.

## Repository Test Coverage

Tests added under `tests/` cover:

- valid AdvisorResult parsing
- invalid verdict rejection
- degraded result validation
- BLOCK and CHANGES_REQUIRED policy mapping
- high severity finding preventing silent PASS
- JSONL receipt roundtrip
- secret-like key redaction
- prompt packet shape
- `advisor_audit` success and degraded error path
- soft gate hook behavior
- subagent/tool receipt capture
- Commander / Worker / Advisor end-to-end flow:
  `A1_PLAN -> A2_DELEGATION -> Worker receipts -> A3_EXCEPTION -> A3_FINAL -> RESOLUTION_GATE`

See `runtime-profile/runbooks/live-smoke.md` for the repeatable runbook.

## Hermes Runtime Checklist

Run after installing/enabling the plugin in the real Hermes environment:

```bash
hermes plugins install poruru210/hermes-runtime/plugin/advisor-gate --enable
hermes config check
hermes doctor
hermes fallback list
hermes plugins list
hermes gateway restart
```

Expected plugin signs:

- `advisor-gate` appears enabled in `hermes plugins list`
- `advisor_audit` appears in available tools
- receipts are written under `~/.hermes/advisor/receipts.jsonl`
- missing `A3_FINAL` causes soft-gate final output

## Target Install Validation

Target-specific deployment scripts, SSH keys, hostnames, and live smoke logs
belong under local `work/` notes and are intentionally not committed.

For a real Hermes install, validate:

```bash
hermes config check
hermes doctor
hermes plugins list
```

Expected registration signs:

```text
advisor-gate: enabled
tools: advisor_audit, advisor_resolution_gate
hooks: subagent_start, subagent_stop, pre_tool_call, post_tool_call,
       transform_llm_output, pre_verify
```

Then run an Advisor smoke through the real Hermes tool registry and confirm an
`A3_FINAL` result can return `policy_action=continue`.

For the focused plugin flow, run:

```bash
uv run --extra dev python -m pytest tests/test_end_to_end_flow.py
```

Expected result:

```text
1 passed
```

## Discord Orchestration Smoke

User-facing prompt:

```text
Please check whether this repository's Advisor Gate is wired correctly for
planning, delegation, worker evidence, exception handling, final audit, and
resolution recording. Use read-only inspection where possible, split the work
only if it is useful, and include concrete evidence before finalizing.
```

The user prompt intentionally does not name Level 1, Level 2, Commander, or
Worker roles. The Commander decides whether delegation is useful. If delegation
is used, inspect `/agents` or `/tasks` while the turn is running.

Pass criteria:

- The user request is natural language, not a topology instruction.
- The Commander records `A1_PLAN` and, if it delegates, `A2_DELEGATION`.
- Advisor audits the chosen delegation plan; it does not choose the worker count
  or decomposition units.
- Worker child receipts include `child_session_id` and `child_role`.
- Worker scope stays narrow and evidence-focused.
- `subagent_start` / `subagent_stop` receipts are written.
- `A3_FINAL` receipt exists and verdict is `PASS`.
- `advisor_resolution_gate` is recorded before final delivery.

## Current Limitation

Gateway or Desktop validation remains target-specific. Record hostnames,
tokens, local paths, and live logs only in ignored local notes.
