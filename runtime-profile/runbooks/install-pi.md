# Pi Install Runbook

Target host:

- `pi@10.1.20.11`
- Repository checkout: `/home/pi/hermes-runtime`
- Hermes service: `hermes-serve.service`

## Update Runtime Repository

```bash
cd /home/pi/hermes-runtime
git pull --ff-only
mise run check
uv run --extra dev python -m pytest tests/test_end_to_end_flow.py
```

## Install Advisor Gate Plugin

Use the official Hermes plugin installer:

```bash
hermes plugins install poruru210/hermes-runtime/plugin/advisor-gate --force --enable
```

Then restart Hermes:

```bash
hermes gateway restart
```

If the official restart command hangs, use systemd on the Pi:

```bash
sudo systemctl restart hermes-serve.service
```

## Verify

```bash
systemctl is-active hermes-serve.service
hermes config check
hermes doctor
hermes plugins list --plain --no-bundled
hermes tools list
```

Expected signs:

- `hermes-serve.service` is `active`.
- `advisor-gate` is enabled.
- `hermes doctor` reports `advisor_gate` under Tool Availability.
- Repository checks pass.

Do not commit local logs, receipts, auth files, `.env`, or terminal captures
that contain secrets.
