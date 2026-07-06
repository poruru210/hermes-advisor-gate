# AGENTS.md

## Project Purpose

This repository implements a personal Hermes runtime profile:

1. A baseline Hermes topology configuration.
2. Hermes Advisor Gate as a private plugin / skill / receipt-store extension.
3. Commander / Worker / Advisor runtime guidance, runbooks, and validation.

The baseline topology uses official Hermes configuration only.

The Advisor extension provides review-only audits:

- A1_PLAN
- A2_DELEGATION
- A3_EXCEPTION
- A3_FINAL

The Advisor produces structured findings and gate verdicts:

- PASS
- CHANGES_REQUIRED
- BLOCK

## Source Of Truth

Use this order:

1. Current Hermes Agent official docs.
2. Current Hermes Agent source code.
3. This repository's docs.
4. Task prompt.

If docs and source disagree, source wins. If behavior cannot be verified from
docs or source, record it as unresolved instead of inventing an API.

## Core Policy

Do not fork or modify Hermes core unless explicitly asked in a separate task.

This repository must remain a runtime profile plus plugin / skill /
receipt-store implementation unless a later ADR approves a minimal core patch.

## Secrets Policy

Never commit:

- `.env`
- API keys
- OAuth tokens
- auth files
- local Hermes config containing secrets
- receipt logs
- SQLite databases
- terminal logs containing private data

## Advisor Role

Advisor is review-only.

Advisor must not:

- execute shell commands
- modify files
- deploy
- claim that it performed implementation work
- mark unresolved items as resolved without evidence

## Engineering Rules

Prefer small, reviewable changes.

Keep implementation split across:

- `plugin/advisor-gate/`: Advisor tool, hook, schema, policy, packet, receipt-store implementation
- `runtime-profile/config/`: sanitized Hermes runtime config examples
- `runtime-profile/skills/`: Commander, Worker, and Advisor-flow runtime skills
- `runtime-profile/runbooks/`: install, live smoke, and rollback operations
- `runtime-profile/locks/`: non-secret runtime and plugin version locks
- `docs/`: architecture, operations, image compliance, design records
- `tests/`: plugin and runtime-flow verification

Do not mix unrelated phases in one change.

## Test Commands

Run relevant checks after code changes:

```bash
mise run check
```

For Hermes runtime validation, document but do not fake:

```bash
hermes config check
hermes doctor
hermes gateway restart
```

If a command cannot run because tooling is not configured, state that
explicitly and add a follow-up item.

## Definition Of Done

A task is done only when:

- requested files are created or updated
- tests are added or updated where appropriate
- relevant validation commands were run or explicitly documented as not runnable
- failures are reported honestly
- no Hermes core files were changed
- no secrets or local logs were committed
- final response includes files changed, checks run, unresolved items, and next
  recommended task
