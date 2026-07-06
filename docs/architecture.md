# Architecture

This repository is a personal Hermes runtime monorepo.

It is organized around four top-level areas:

```text
plugin/
  advisor-gate/

runtime-profile/
  config/
  skills/
  runbooks/
  locks/

docs/
  image-spec-compliance.md
  architecture.md
  operations.md

tests/
```

## Responsibilities

| Area | Responsibility |
|---|---|
| `plugin/advisor-gate/` | Advisor Gate plugin implementation: tools, hooks, schemas, policy, receipt store |
| `runtime-profile/config/` | Sanitized Hermes runtime configuration examples |
| `runtime-profile/skills/commander/` | Commander behavior guidance for the parent Hermes session |
| `runtime-profile/skills/worker/` | Worker behavior guidance for delegated child sessions |
| `runtime-profile/skills/advisor-flow/` | Advisor audit workflow guidance |
| `runtime-profile/runbooks/` | Pi install, live smoke, and rollback operations |
| `runtime-profile/locks/` | Non-secret runtime and plugin version locks |
| `docs/` | Architecture, operations, image-spec compliance, and historical design records |
| `tests/` | Plugin and runtime-flow verification |

## Role Model

Hermes core is not forked or patched.

Commander and Worker are runtime roles expressed through existing Hermes
behavior:

- Commander: parent Hermes session that interprets the user request, plans,
  delegates if useful, and resolves Advisor findings.
- Worker: child Hermes session created by `delegate_task`.
- Leaf Worker: child with `role="leaf"` that does not delegate further.
- Orchestrator Worker: child with `role="orchestrator"` that may coordinate its
  own children when justified.
- Advisor: review-only plugin tools and hooks implemented by
  `plugin/advisor-gate`.

Advisor does not choose decomposition, worker count, or Worker assignments. It
audits the Commander-selected plan, delegation, evidence, exception handling,
and final answer.

## Source Of Truth

Use this order:

1. Current Hermes Agent official docs.
2. Current Hermes Agent source code.
3. This repository's docs and runtime profile.
4. Task prompt.

If docs and source disagree, source wins. If behavior cannot be verified from
docs or source, record it as unresolved.

## No-Core-Patch Policy

This runtime profile must stay inside official Hermes configuration, plugin,
hook, and skill surfaces unless a future ADR explicitly approves a minimal core
patch.

Historical design notes remain under `docs/` for traceability.
