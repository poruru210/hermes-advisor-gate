# Rollback Runbook

Use this when the runtime profile or Advisor Gate plugin must be rolled back on
the Pi.

## Roll Back Repository Checkout

Choose a known-good commit from Git history:

```bash
cd /home/pi/hermes-runtime
git log --oneline -10
git checkout <known-good-commit>
```

Validate before reinstalling:

```bash
mise run check
uv run --extra dev python -m pytest tests/test_end_to_end_flow.py
```

## Reinstall Plugin From Checked-Out State

The official Hermes installer installs from GitHub. If the known-good commit is
already pushed, prefer installing the matching branch or tag from GitHub.

```bash
hermes plugins install poruru210/hermes-runtime/plugin/advisor-gate --force --enable
```

Restart Hermes:

```bash
hermes gateway restart
```

If needed:

```bash
sudo systemctl restart hermes-serve.service
```

## Disable Plugin

If rollback is not enough and the plugin must be removed from the active path:

```bash
hermes plugins disable advisor-gate
sudo systemctl restart hermes-serve.service
```

## Verify

```bash
systemctl is-active hermes-serve.service
hermes doctor
hermes plugins list --plain --no-bundled
```

Record the rollback reason and final commit in local notes. Do not commit logs,
receipts, auth files, or secrets.
