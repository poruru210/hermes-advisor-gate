"""JSONL receipt store for Advisor Gate."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from advisor_gate.schemas import (
    AdvisorPhase,
    AdvisorResult,
    ResolutionGate,
    resolution_gate_from_dict,
    resolution_gate_to_dict,
    result_from_dict,
    result_to_dict,
)

SECRET_KEY_PARTS = ("token", "secret", "api_key", "apikey", "password", "auth")


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_s = str(key)
            if any(part in key_s.lower() for part in SECRET_KEY_PARTS):
                redacted[key_s] = "[REDACTED]"
            else:
                redacted[key_s] = redact_secrets(item)
        return redacted
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return [redact_secrets(item) for item in value]
    return value


def default_receipt_path() -> Path:
    return Path("~/.hermes/advisor/receipts.jsonl").expanduser()


@dataclass
class ReceiptStore:
    path: Path

    @classmethod
    def from_path(cls, raw_path: str | Path | None = None) -> ReceiptStore:
        return cls(Path(raw_path).expanduser() if raw_path else default_receipt_path())

    def append(self, entry: dict[str, Any]) -> dict[str, Any]:
        safe_entry = cast(dict[str, Any], redact_secrets(entry))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(safe_entry, ensure_ascii=False, sort_keys=True) + "\n")
        return safe_entry

    def append_result(
        self,
        *,
        session_id: str,
        result: AdvisorResult,
        source: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "timestamp": utc_now_iso(),
            "session_id": session_id,
            "phase": result.phase.value,
            "verdict": result.verdict.value,
            "findings": [item for item in result_to_dict(result)["findings"]],
            "known_unresolved": list(result.known_unresolved),
            "degraded": result.degraded,
            "error_class": result.error_class,
            "diagnostics": list(result.diagnostics),
            "unavailable_reason": result.unavailable_reason,
            "final_improvement": result.final_improvement,
            "source": source,
        }
        if extra:
            entry["extra"] = extra
        return self.append(entry)

    def append_resolution_gate(
        self,
        *,
        session_id: str,
        gate: ResolutionGate,
        source: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "timestamp": utc_now_iso(),
            "session_id": session_id,
            "phase": "RESOLUTION_GATE",
            "source": source,
            "resolution_gate": resolution_gate_to_dict(gate),
        }
        if extra:
            entry["extra"] = extra
        return self.append(entry)

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        entries: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                entries.append(json.loads(line))
        return entries

    def iter_session(self, session_id: str) -> Iterable[dict[str, Any]]:
        for entry in self.read_all():
            if entry.get("session_id") == session_id:
                yield entry

    def latest_result(
        self,
        *,
        session_id: str,
        phase: AdvisorPhase | str = AdvisorPhase.A3_FINAL,
    ) -> AdvisorResult | None:
        phase_value = AdvisorPhase(str(phase)).value
        for entry in reversed(self.read_all()):
            if entry.get("session_id") != session_id or entry.get("phase") != phase_value:
                continue
            try:
                return result_from_dict(
                    {
                        "phase": entry["phase"],
                        "verdict": entry["verdict"],
                        "findings": entry.get("findings", []),
                        "known_unresolved": entry.get("known_unresolved", []),
                        "degraded": entry.get("degraded", False),
                        "error_class": entry.get("error_class"),
                        "diagnostics": entry.get("diagnostics", []),
                        "unavailable_reason": entry.get("unavailable_reason", ""),
                        "final_improvement": entry.get("final_improvement", ""),
                    }
                )
            except (KeyError, ValueError):
                continue
        return None

    def latest_resolution_gate(self, *, session_id: str) -> ResolutionGate | None:
        for entry in reversed(self.read_all()):
            if entry.get("session_id") != session_id or entry.get("phase") != "RESOLUTION_GATE":
                continue
            try:
                raw_gate = entry.get("resolution_gate")
                if not isinstance(raw_gate, dict):
                    continue
                return resolution_gate_from_dict(raw_gate)
            except ValueError:
                continue
        return None

    def is_child_session(self, session_id: str) -> bool:
        if not session_id:
            return False
        for entry in reversed(self.read_all()):
            if entry.get("source") not in {"subagent_start", "subagent_stop"}:
                continue
            extra = entry.get("extra")
            if isinstance(extra, dict) and extra.get("child_session_id") == session_id:
                return True
        return False

    def active_child_sessions(self, parent_session_id: str) -> tuple[str, ...]:
        if not parent_session_id:
            return ()
        active: set[str] = set()
        for entry in self.read_all():
            if entry.get("session_id") != parent_session_id:
                continue
            if entry.get("source") not in {"subagent_start", "subagent_stop"}:
                continue
            extra = entry.get("extra")
            if not isinstance(extra, dict):
                continue
            child_session_id = str(extra.get("child_session_id") or "")
            if not child_session_id:
                continue
            if entry.get("source") == "subagent_start":
                active.add(child_session_id)
            else:
                active.discard(child_session_id)
        return tuple(sorted(active))

    def has_active_child_session(self, parent_session_id: str) -> bool:
        return bool(self.active_child_sessions(parent_session_id))
