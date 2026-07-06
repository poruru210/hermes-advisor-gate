# Hermes Advisor Gate

This workspace contains:

- an official-Hermes baseline topology config and validation runbook
- a private Advisor Gate plugin, skill, and JSONL receipt store

Hermes core is not forked or patched. Advisor Gate uses official Hermes plugin
surfaces only.

## Baseline Hermes topology

- Main agent: `openai-codex` with `gpt-5.5`, high reasoning.
- Delegated workers: `openai-codex` with `gpt-5.3-codex-spark`, medium
  reasoning.
- Level 1 workers can be orchestrators when `delegate_task(role="orchestrator")`
  is used.
- Level 2 workers are leaves when `delegate_task(role="leaf")` is used.
- Delegation is capped at three concurrent children and depth two.
- Compression uses the main model through `auxiliary.compression.provider: main`.
- Fallback uses `zai` with `glm-4.7`.
- Smart routing is disabled by omitting `provider_routing`.

See `docs/hermes-baseline-topology.md` for the verification table.

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
baseline topology plus Advisor overlay. A1/A2 pre-action enforcement uses the
official Hermes `pre_tool_call` plugin hook and requires same-turn Advisor
receipts when Hermes provides a `turn_id`. A3 final checks use official
`pre_verify` for coding turns plus `transform_llm_output` as a soft fallback.

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
hermes plugins install poruru210/hermes-advisor-gate/plugin/advisor-gate --enable
```

The installer clones only `plugin/advisor-gate`, so that directory is
self-contained and includes both `plugin.yaml` / `__init__.py` and the
`advisor_gate` Python package.

Merge `config/advisor-gate.example.yaml` into the real Hermes config. Leave
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

From a new Discord thread, ask Hermes:

```text
Create one Level 1 orchestrator subagent. The orchestrator should decompose
this into exactly three Level 2 leaf workers. Each leaf should inspect a
different small, read-only aspect of the workspace and return a concise result.
Do not spawn any Level 3 agents. After dispatch, run advisor_audit for A3_FINAL
with the observed tree, evidence, known unresolved items, and final draft.
```

Expected `/agents` or `/tasks` shape while the turn is running:

```text
main agent
  level 1 orchestrator
    level 2 leaf worker 1
    level 2 leaf worker 2
    level 2 leaf worker 3
```

The orchestration passes only if the Level 1 child can delegate to three leaf
children, Level 2 children do not spawn Level 3, subagent receipts are written,
and an `A3_FINAL` Advisor receipt exists before final delivery.
