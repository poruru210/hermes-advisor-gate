# Implementation Plan

## Completed

- Phase 0: official Hermes config/source research.
- Phase 1: sanitized baseline config and validation runbook.
- Phase 2: Advisor Gate skeleton, ADRs, plugin contract.
- Phase 3: pure Python schemas, policy, packets, receipt store.
- Phase 4: `advisor_audit` tool MVP using `ctx.llm.complete_structured`.
- Phase 5: hook-based receipts and soft gate.
- Phase 6: validation docs and no-core plugin decision docs.
- Phase 7: Advisor ResolutionGate.
- Phase 8: official `pre_tool_call` A1/A2 gate for configured action tools and
  `delegate_task`.
- Phase 9: final-gate enforcement that observed tool/runtime failures must have
  a later passing `A3_EXCEPTION` audit.
- Phase 10: receipt freshness enforcement for same-turn A1/A2 and event-fresh
  A3-Final.
- Phase 11: Advisor tool context capture through `pre_tool_call`, so same-turn
  receipts do not require Hermes registry handler changes.

## Current Artifact Map

- `plugin/advisor-gate/plugin.yaml`: official Hermes directory-plugin manifest.
- `plugin/advisor-gate/__init__.py`: directory-plugin wrapper.
- `plugin/advisor-gate/advisor_gate/schemas.py`: Advisor phases, verdicts,
  findings, result schema, FinalPayload, and ResolutionGate.
- `plugin/advisor-gate/advisor_gate/policy.py`: PASS / CHANGES_REQUIRED /
  BLOCK policy mapping.
- `plugin/advisor-gate/advisor_gate/packets.py`: prompt packet builders.
- `plugin/advisor-gate/advisor_gate/store.py`: JSONL receipt store and
  redaction.
- `plugin/advisor-gate/advisor_gate/registration.py`: Hermes plugin
  registration.
- `plugin/advisor-gate/advisor_gate/config.py`: Advisor Gate config loading.
- `plugin/advisor-gate/advisor_gate/audit_handlers.py`: `advisor_audit` tool
  handling.
- `plugin/advisor-gate/advisor_gate/resolution_handlers.py`:
  `advisor_resolution_gate` tool handling.
- `plugin/advisor-gate/advisor_gate/event_hooks.py`: observer hooks for
  subagents and tool results.
- `plugin/advisor-gate/advisor_gate/pre_tool_gate.py`: A1/A2 `pre_tool_call`
  enforcement.
- `plugin/advisor-gate/advisor_gate/final_gate.py`: A3 exception/final
  verification and soft gate.
- `plugin/advisor-gate/advisor_gate/receipt_queries.py`: receipt lookup and
  freshness helpers.
- `runtime-profile/skills/advisor-flow/SKILL.md`: agent-facing workflow guidance.
- `runtime-profile/config/hermes.config.example.yaml`: official topology config.
- `runtime-profile/config/advisor-gate.example.yaml`: plugin config example.
- `tests/`: unit and hook tests.

## Runtime Sequence

1. Hermes loads `advisor-gate` from plugin discovery.
2. `register(ctx)` registers `advisor_audit`, `advisor_resolution_gate`, and
   the Advisor hooks.
3. Acting agent calls `advisor_audit` with phase and packet.
4. Plugin calls `ctx.llm.complete_structured()` with AdvisorResult schema.
5. Plugin validates result, writes JSONL receipt, and returns JSON to Hermes.
6. `pre_tool_call` blocks configured action tools and unclassified tools until
   same-turn A1 passes, and blocks `delegate_task` until same-turn A2 passes.
   For Advisor tools themselves, it records tool context for receipt freshness.
7. Subagent/tool hooks write evidence receipts.
8. Failed tool/runtime events are marked as requiring `A3_EXCEPTION`; final
   gates continue the Commander loop until a later A3-Exception audit passes.
9. `pre_verify` nudges coding turns when `A3_EXCEPTION` or `A3_FINAL` is
   missing or failing.
10. While background subagents are active, final gating is deferred so Hermes'
   official background delegation flow can return provisional progress.
11. `pre_verify` returns the Commander to the same loop if the current final
    draft lacks a matching passing `A3_FINAL` receipt written after the latest
    relevant event, or lacks a current `ResolutionGate`.
12. `transform_llm_output` remains a fallback delivery guard.

## Remaining Runtime Work

Actual Discord/gateway validation must be run in the target Hermes install after
the plugin is applied. The local repository verifies code paths with compile
checks and smoke checks but cannot prove account-specific model access.
