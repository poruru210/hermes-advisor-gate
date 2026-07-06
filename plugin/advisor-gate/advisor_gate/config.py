"""Configuration loading for Advisor Gate."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, cast

DEFAULT_A1_ACTION_TOOL_NAMES = (
    "apply_patch",
    "delegate_task",
    "edit_file",
    "execute_code",
    "patch",
    "send_message",
    "terminal",
    "write_file",
)
DEFAULT_A1_EXEMPT_TOOL_NAMES = (
    "advisor_audit",
    "advisor_resolution_gate",
    "browser_snapshot",
    "find_files",
    "list_files",
    "read_file",
    "search_files",
    "view",
    "web_extract",
    "web_search",
)
DEFAULT_A1_EXEMPT_TOOL_PREFIXES: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdvisorGateConfig:
    enabled: bool = True
    provider: str = ""
    model: str = ""
    max_input_chars: int = 64_000
    receipt_path: str = "~/.hermes/advisor/receipts.jsonl"
    require_a1_before_action: bool = True
    require_a2_before_delegation: bool = True
    a1_action_tool_names: tuple[str, ...] = DEFAULT_A1_ACTION_TOOL_NAMES
    a1_exempt_tool_names: tuple[str, ...] = DEFAULT_A1_EXEMPT_TOOL_NAMES
    a1_exempt_tool_prefixes: tuple[str, ...] = DEFAULT_A1_EXEMPT_TOOL_PREFIXES
    gate_unclassified_tools_before_a1: bool = True
    require_a3_exception: bool = True
    require_a3_final: bool = True
    require_resolution_gate: bool = True
    gate_subagents: bool = False
    defer_while_subagents_active: bool = True


def load_plugin_config() -> AdvisorGateConfig:
    try:
        load_config = import_module("hermes_cli.config").load_config
        config = load_config() or {}
    except Exception:
        config = {}

    config_dict = config if isinstance(config, dict) else {}
    raw_value = config_dict.get("advisor_gate")
    raw = cast(dict[str, Any], raw_value) if isinstance(raw_value, dict) else {}

    soft_gate_value = raw.get("soft_gate")
    soft_gate = (
        cast(dict[str, Any], soft_gate_value) if isinstance(soft_gate_value, dict) else {}
    )
    pre_action_gate_value = raw.get("pre_action_gate")
    pre_action_gate = (
        cast(dict[str, Any], pre_action_gate_value)
        if isinstance(pre_action_gate_value, dict)
        else {}
    )

    def _int_value(key: str, default: int) -> int:
        try:
            return int(raw.get(key, default) or default)
        except (TypeError, ValueError):
            return default

    configured_action_tools = pre_action_gate.get("a1_action_tool_names")
    if isinstance(configured_action_tools, list):
        action_tool_names = tuple(
            str(item).strip() for item in configured_action_tools if str(item).strip()
        )
    else:
        action_tool_names = DEFAULT_A1_ACTION_TOOL_NAMES
    configured_exempt_tools = pre_action_gate.get("a1_exempt_tool_names")
    if isinstance(configured_exempt_tools, list):
        exempt_tool_names = tuple(
            str(item).strip() for item in configured_exempt_tools if str(item).strip()
        )
    else:
        exempt_tool_names = DEFAULT_A1_EXEMPT_TOOL_NAMES
    configured_exempt_prefixes = pre_action_gate.get("a1_exempt_tool_prefixes")
    if isinstance(configured_exempt_prefixes, list):
        exempt_tool_prefixes = tuple(
            str(item).strip() for item in configured_exempt_prefixes if str(item).strip()
        )
    else:
        exempt_tool_prefixes = DEFAULT_A1_EXEMPT_TOOL_PREFIXES

    return AdvisorGateConfig(
        enabled=bool(raw.get("enabled", True)),
        provider=str(raw.get("provider") or "").strip(),
        model=str(raw.get("model") or "").strip(),
        max_input_chars=_int_value(
            "max_input_chars",
            _int_value("max_total_input_chars_per_turn", 64_000),
        ),
        receipt_path=str(raw.get("receipt_path") or "~/.hermes/advisor/receipts.jsonl"),
        require_a1_before_action=bool(pre_action_gate.get("require_a1_before_action", True)),
        require_a2_before_delegation=bool(
            pre_action_gate.get("require_a2_before_delegation", True)
        ),
        a1_action_tool_names=action_tool_names,
        a1_exempt_tool_names=exempt_tool_names,
        a1_exempt_tool_prefixes=exempt_tool_prefixes,
        gate_unclassified_tools_before_a1=bool(
            pre_action_gate.get("gate_unclassified_tools_before_a1", True)
        ),
        require_a3_exception=bool(soft_gate.get("require_a3_exception", True)),
        require_a3_final=bool(soft_gate.get("require_a3_final", True)),
        require_resolution_gate=bool(soft_gate.get("require_resolution_gate", True)),
        gate_subagents=bool(soft_gate.get("gate_subagents", False)),
        defer_while_subagents_active=bool(soft_gate.get("defer_while_subagents_active", True)),
    )
