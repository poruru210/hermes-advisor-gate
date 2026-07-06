# Integration Validation

## Local Checks Run

```bash
mise run check
```

Result:

```text
compile: success
pytest: 55 passed
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

## Hermes Runtime Checklist

Run after installing/enabling the plugin in the real Hermes environment:

```bash
hermes plugins install poruru210/hermes-advisor-gate/plugin/advisor-gate --enable
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

## Discord Orchestration Smoke

Prompt:

```text
Create one Level 1 orchestrator subagent. The orchestrator should decompose
this into exactly three Level 2 leaf workers. Each leaf should inspect a
different small, read-only aspect of the workspace and return a concise result.
Do not spawn any Level 3 agents. After dispatch, run advisor_audit for A3_FINAL
with the observed tree, evidence, known unresolved items, and final draft.
```

Expected `/agents` or `/tasks` shape:

```text
main agent
  level 1 orchestrator
    level 2 leaf worker 1
    level 2 leaf worker 2
    level 2 leaf worker 3
```

Pass criteria:

- Level 1 child has orchestrator role.
- Exactly three Level 2 leaves appear.
- Level 2 leaves do not spawn Level 3.
- `subagent_start` / `subagent_stop` receipts are written.
- `A3_FINAL` receipt exists and verdict is `PASS`.

## Current Limitation

Gateway or Desktop validation remains target-specific. Record hostnames,
tokens, local paths, and live logs only in ignored local notes.
