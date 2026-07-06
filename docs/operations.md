# Operations

Operational assets live under `runtime-profile/`.

## Install And Update

Use:

- `runtime-profile/runbooks/install-pi.md`

The Pi checkout should be:

```text
/home/pi/hermes-runtime
```

Install the Advisor Gate plugin through the official Hermes installer:

```bash
hermes plugins install poruru210/hermes-runtime/plugin/advisor-gate --force --enable
```

## Runtime Skills

Install or reference these runtime skills as appropriate for the Hermes
environment:

- `runtime-profile/skills/commander/SKILL.md`
- `runtime-profile/skills/worker/SKILL.md`
- `runtime-profile/skills/advisor-flow/SKILL.md`

The user should provide natural-language requests. Commander and Worker behavior
is guided by runtime skills, not by asking the user to prescribe internal
topology.

## Validation

Repository checks:

```bash
mise run check
```

Focused runtime-flow check:

```bash
uv run --extra dev python -m pytest tests/test_end_to_end_flow.py
```

Live smoke:

- `runtime-profile/runbooks/live-smoke.md`

Rollback:

- `runtime-profile/runbooks/rollback.md`

## Locks

Non-secret runtime locks:

- `runtime-profile/locks/plugins.lock`
- `runtime-profile/locks/hermes-version.lock`

These files record expected runtime and plugin sources. They must not contain
tokens, auth files, logs, receipts, or host-private configuration.

## Secrets

Never commit:

- `.env`
- API keys
- OAuth tokens
- auth files
- local Hermes config containing secrets
- receipt logs
- SQLite databases
- terminal logs containing private data
