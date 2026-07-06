# Hermes Baseline Topology

## Purpose

This document maps the requested baseline topology to official Hermes Agent
configuration and runtime behavior. It covers only official Hermes features:
model selection, subagent delegation, auxiliary compression, fallback providers,
Discord gateway behavior, and runtime inspection.

Hermes core remains unmodified. Advisor Gate is out of scope for this phase.
Phase 1 adds the runbook needed to apply and validate the official baseline.

## Upstream

- Hermes Agent repo: https://github.com/NousResearch/hermes-agent
- Inspected commit: `beaa1a08e6abf2fb8efff0b05da8857bef21ce1f`
- Docs inspected on: 2026-07-06 Asia/Tokyo
- Model catalog `updated_at`: `2026-07-01T20:08:52Z`

## Verified Config Keys

| Area | Key or API | Status | Source |
|---|---|---:|---|
| Main model | `model.provider` | verified | docs, `cli-config.yaml.example` |
| Main model | `model.default` | verified | docs, `hermes_cli/config.py` |
| Main reasoning | `agent.reasoning_effort` | verified | docs, `cli-config.yaml.example` |
| Main max turns | `agent.max_turns` | verified | `hermes_cli/config.py` |
| Delegation model | `delegation.provider` | verified | docs, `tools/delegate_tool.py` |
| Delegation model | `delegation.model` | verified | docs, `tools/delegate_tool.py` |
| Delegation loop | `delegation.max_iterations` | verified | docs, `hermes_cli/config.py` |
| Delegation reasoning | `delegation.reasoning_effort` | verified | `tools/delegate_tool.py` |
| Delegation concurrency | `delegation.max_concurrent_children` | verified | docs, `tools/delegate_tool.py` |
| Delegation depth | `delegation.max_spawn_depth` | verified | docs, `tools/delegate_tool.py` |
| Delegation role gate | `delegation.orchestrator_enabled` | verified | docs, `tools/delegate_tool.py` |
| Delegation timeout | `delegation.child_timeout_seconds` | verified | docs, `tools/delegate_tool.py` |
| Child role | `delegate_task(role="leaf"|"orchestrator")` | verified | docs, `tools/delegate_tool.py` |
| Compression model | `auxiliary.compression.provider/model` | verified | docs, `hermes_cli/config.py` |
| Fallback chain | `fallback_providers` | verified | docs, `hermes_cli/config.py` |
| Runtime tree | `/agents`, `/tasks` alias | verified | delegation docs, `hermes_cli/cli_commands_mixin.py` |
| Discord behavior | top-level `discord.*` settings | verified | Discord docs, `cli-config.yaml.example` |

## Provider And Model Names

| Provider/model | Status | Notes |
|---|---:|---|
| `openai-codex` | verified | Provider key appears in docs/source. |
| `gpt-5.5` under `openai-codex` | requires runtime check | Source includes it in `DEFAULT_CODEX_MODELS`; account entitlement must be verified. |
| `gpt-5.3-codex-spark` under `openai-codex` | requires runtime check | Source says this is a Codex OAuth research-preview model exposed only through the Codex backend for eligible accounts. |
| `zai` | verified | Provider key appears in docs/source. |
| `glm-4.7` under `zai` | requires runtime check | Source includes it in the `zai` model list; live availability can depend on the key/endpoint. |

## Topology Mapping

| Image element | Hermes implementation | Config/tool key | Verification method | Status |
|---|---|---|---|---:|
| Discord Gateway / current thread | Hermes messaging gateway Discord adapter | `discord.*`, `.env` Discord credentials | Send from a new Discord thread/channel and inspect gateway logs | requires runtime check |
| Level 0 Main Agent | Primary Hermes agent | `model.provider`, `model.default`, `agent.reasoning_effort` | `hermes config`, `hermes doctor`, model status | verified |
| Main reasoning high | Main agent reasoning setting | `agent.reasoning_effort: high` | `/reasoning` or config dump | verified |
| Context budget | Operational/model context limit, not a single topology key | `model.context_length` only if overriding detected context | `hermes doctor`, runtime context display | requires runtime check |
| Level 1 Worker / Orchestrator | Child agent spawned by `delegate_task` | `delegate_task(role="orchestrator")` | `/agents` or `/tasks` tree during smoke test | verified |
| Level 1 model override | Delegation model/provider override | `delegation.provider`, `delegation.model` | `hermes config`, child status/logs | verified |
| Level 1 reasoning medium | Delegation reasoning override | `delegation.reasoning_effort: medium` | config plus child runtime logs if exposed | verified |
| Max concurrent children 3 | Batch/background delegation cap | `delegation.max_concurrent_children: 3` | submit 3-worker fanout, then check `/agents` | verified |
| Level 2 leaf workers | Grandchildren spawned by Level 1 orchestrator | `max_spawn_depth: 2`, child calls `role="leaf"` | `/agents` or `/tasks` tree | verified |
| Leaf cannot spawn further | Default child role behavior and blocked toolsets | `role="leaf"` default | ask for nested spawn attempt and inspect result | verified |
| Orchestrator enabled | Allows child to retain delegation toolset | `delegation.orchestrator_enabled: true` | Level 1 orchestrator successfully spawns leaves | verified |
| Child timeout 600s | Optional hard cap | `delegation.child_timeout_seconds: 600` | long-running child test or config inspection | verified |
| Compression | Auxiliary compression route | `auxiliary.compression.provider/model` | force/observe compression, inspect logs | verified |
| Smart routing disabled | Omit OpenRouter routing preferences | no `provider_routing` key | inspect config | verified |
| Fallback | Primary fallback chain | `fallback_providers` | `hermes fallback list`, induced provider failure if safe | verified |

## Baseline Config

Use `runtime-profile/config/hermes.config.example.yaml` as a sanitized example. It contains no
secrets. Copy only the relevant non-secret settings into `~/.hermes/config.yaml`
or a Hermes profile config after reviewing runtime availability.

Important deviations from the initial sketch:

- `delegation.max_spawn_depth` defaults to `1` in current source, so the
  topology needs `max_spawn_depth: 2` to permit orchestrator children to spawn
  Level 2 leaves.
- `delegation.child_timeout_seconds` defaults to `0`, meaning no hard timeout.
  The topology's 600 second cap is an explicit opt-in.
- `provider: main` is valid for auxiliary tasks, not for top-level
  `model.provider`.
- `display.platforms.discord.cleanup_progress` was not confirmed and is not in
  the Phase 1 example.

## Apply Runbook

Back up any existing Hermes config before applying the baseline.

Windows PowerShell example:

```powershell
Copy-Item -LiteralPath "$env:USERPROFILE\.hermes\config.yaml" -Destination "$env:USERPROFILE\.hermes\config.yaml.backup" -ErrorAction SilentlyContinue
Copy-Item -LiteralPath ".\runtime-profile\config\hermes.config.example.yaml" -Destination "$env:USERPROFILE\.hermes\config.yaml"
```

Linux or macOS symlink example, only if this repository path is stable:

```bash
ln -s "$(pwd)/runtime-profile/config/hermes.config.example.yaml" ~/.hermes/config.yaml
```

For an existing production Hermes config, prefer merging the non-secret sections
manually instead of overwriting the file.

## Validation Commands

Documented expected commands:

```bash
hermes config check
hermes doctor
hermes gateway restart
```

Useful read-only inspection commands:

```bash
hermes config
hermes fallback list
hermes chat --list-toolsets
```

Runtime inspection during a turn:

```text
/agents
/tasks
```

## Runtime Topology Diagnostic

This is an operator-only topology diagnostic, not a normal user-facing smoke
test. It intentionally prescribes internal delegation shape to verify that the
baseline Hermes delegation depth and `child_role` behavior work as configured.
The three leaf workers in this diagnostic are a fanout probe for the configured
concurrency cap. They are not a product requirement and are not the Advisor's
chosen decomposition units.

For normal Advisor smoke tests, use a natural-language request and let the
Commander decide whether delegation is useful.

From a new diagnostic Discord thread, ask Hermes:

```text
Create one Level 1 orchestrator subagent. The orchestrator should decompose
this into exactly three Level 2 leaf workers. Each leaf should inspect a
different small, read-only aspect of the workspace and return a concise result.
Do not spawn any Level 3 agents. After dispatch, report the observed agent tree.
```

While the turn is running, inspect:

```text
/agents
```

or:

```text
/tasks
```

Expected shape:

```text
main agent
  level 1 orchestrator
    level 2 leaf worker 1
    level 2 leaf worker 2
    level 2 leaf worker 3
```

The diagnostic passes only if the Level 1 child is an orchestrator and the
Level 2 children are leaves. It fails if the Level 1 child cannot call
`delegate_task`, if any Level 2 child can spawn Level 3, or if the active tree
cannot be observed.

## No-Secrets Guidance

Do not commit:

- `~/.hermes/.env`
- `~/.hermes/auth.json`
- `DISCORD_BOT_TOKEN`
- `DISCORD_ALLOWED_USERS`
- `DISCORD_ALLOWED_ROLES`
- OAuth refresh tokens
- provider API keys such as `GLM_API_KEY`
- Hermes logs, sessions, or receipt stores

## Known Limitations

- Account-specific model access cannot be proven from source alone.
- Discord thread behavior depends on bot permissions, server settings, channel
  type, and gateway runtime state.
- The baseline config is not a guarantee that every provider accepts every model
  on the target account; run the validation commands before relying on it.
- Advisor Gate is not represented here.
