# Hermes Runtime

This workspace contains:

- an official-Hermes baseline topology config and validation runbook
- a private Advisor Gate plugin, skill, and JSONL receipt store
- personal Hermes runtime profile guidance for Commander / Worker / Advisor flow

Hermes core is not forked or patched. Advisor Gate uses official Hermes plugin
surfaces only.

## Repository Layout

```text
plugin/
  advisor-gate/          # Advisor Plugin implementation

runtime-profile/
  config/                # sanitized Hermes config examples
  skills/                # Commander / Worker / Advisor flow skills
  runbooks/              # Pi install, live smoke, rollback
  locks/                 # non-secret runtime/plugin locks

docs/                    # architecture, operations, compliance, design notes
tests/                   # plugin and runtime-flow verification
```

## Baseline Hermes topology

- Main agent: `openai-codex` with `gpt-5.5`, high reasoning.
- Delegated workers: `openai-codex` with `gpt-5.3-codex-spark`, medium
  reasoning.
- Level 1 workers can be orchestrators when `delegate_task(role="orchestrator")`
  is used.
- Level 2 workers are leaves when `delegate_task(role="leaf")` is used.
- Delegation is capped at three concurrent children and depth two.
- The cap of three concurrent children is an upper bound, not a requirement to
  create three workers. The Commander decides whether delegation is useful and
  how many workers are justified by the task.
- Compression uses the main model through `auxiliary.compression.provider: main`.
- Fallback uses `zai` with `glm-4.7`.
- Smart routing is disabled by omitting `provider_routing`.

See `docs/hermes-baseline-topology.md` for the verification table.
See `docs/architecture.md` for the runtime monorepo architecture and
`docs/operations.md` for operational entry points.

## Advisor Gate

Advisor Gate adds a review-only audit tool and soft-gate hooks:

- `advisor_audit` tool
- `advisor_resolution_gate` tool
- `subagent_start` / `subagent_stop` receipt capture
- `pre_tool_call` A1/A2 pre-action gate
- `post_tool_call` evidence capture
- `A3_EXCEPTION` gate for observed tool/runtime failures
- `pre_verify` continuation nudge for coding turns
- `transform_llm_output` final-response soft gate

See `docs/advisor-topology-fit.md` for the fit/gap analysis against the
baseline topology plus Advisor overlay. See `docs/image-spec-compliance.md` for
the formal compliance table against the source image specification, and
`docs/image-spec-remediation-plan.md` for the prioritized split between plugin,
caller skill, and Hermes core follow-up work. See
`runtime-profile/runbooks/live-smoke.md` for the Commander / Worker / Advisor
flow validation. A1/A2 pre-action enforcement uses the official Hermes
`pre_tool_call` plugin hook and requires same-turn Advisor receipts when Hermes
provides a `turn_id`. A3 final checks use official `pre_verify` for coding turns
plus `transform_llm_output` as a soft fallback.

Advisor phases:

- `A1_PLAN`
- `A2_DELEGATION`
- `A3_EXCEPTION`
- `A3_FINAL`

Verdicts:

- `PASS`
- `CHANGES_REQUIRED`
- `BLOCK`

## Install / Enable

Install the directory plugin through the official Hermes plugin installer:

```bash
hermes plugins install poruru210/hermes-runtime/plugin/advisor-gate --enable
```

The installer clones only `plugin/advisor-gate`, so that directory is
self-contained and includes both `plugin.yaml` / `__init__.py` and the
`advisor_gate` Python package.

Merge `runtime-profile/config/advisor-gate.example.yaml` into the real Hermes config. Leave
`advisor_gate.provider` and `advisor_gate.model` empty unless the plugin LLM
trust gate explicitly allows overrides; empty values make the Advisor use the
active Hermes model, which is the safest fallback when a requested model is not
available.

No Hermes core patch is required. Enable the plugin and merge the Advisor config
only.

## Do not commit

- `~/.hermes/.env`
- `~/.hermes/auth.json`
- `DISCORD_BOT_TOKEN`
- `DISCORD_ALLOWED_USERS`
- `DISCORD_ALLOWED_ROLES`
- OAuth refresh tokens
- provider API keys such as `GLM_API_KEY`
- Advisor receipt JSONL files
- Hermes logs, sessions, or local databases

## Validate

Repository checks:

```bash
mise run check
```

Individual checks:

```bash
mise run test
mise run lint
mise run typecheck
uv run --extra dev python -m pytest tests/test_end_to_end_flow.py
```

Hermes checks after applying config:

```bash
hermes config check
hermes doctor
hermes fallback list
hermes gateway restart
hermes plugins list
```

During a delegated turn, inspect the active tree with either command:

```text
/agents
/tasks
```

## Discord smoke test

From a new Discord thread, ask Hermes as a normal user. Do not prescribe the
internal Commander / Worker topology in the user prompt:

```text
Please check whether this repository's Advisor Gate is wired correctly for
planning, delegation, worker evidence, exception handling, final audit, and
resolution recording. Use read-only inspection where possible, split the work
only if it is useful, and include concrete evidence before finalizing.
```

Expected behavior:

- The user speaks in natural language only.
- The Commander decides whether delegation is useful.
- Advisor audits the Commander plan and delegation evidence; it does not choose
  the worker count or assign decomposition units.
- If delegation is used, `/agents` or `/tasks` shows the parent/child shape.
- Worker receipts include `child_session_id` and `child_role`.
- Worker scope stays narrow and evidence-focused.
- `A3_FINAL` and `advisor_resolution_gate` receipts exist before final delivery.

Use `runtime-profile/runbooks/live-smoke.md` for deterministic plugin-level
validation of the full Commander / Worker / Advisor sequence.
