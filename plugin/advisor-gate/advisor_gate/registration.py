"""Hermes plugin registration for Advisor Gate."""

from __future__ import annotations

from typing import Any

from advisor_gate.audit_handlers import advisor_audit_handler
from advisor_gate.config import load_plugin_config
from advisor_gate.event_hooks import on_post_tool_call, on_subagent_start, on_subagent_stop
from advisor_gate.final_gate import on_pre_verify, on_transform_llm_output
from advisor_gate.pre_tool_gate import on_pre_tool_call
from advisor_gate.resolution_handlers import advisor_resolution_gate_handler
from advisor_gate.store import ReceiptStore
from advisor_gate.tool_schemas import (
    ADVISOR_AUDIT_SCHEMA,
    ADVISOR_RESOLUTION_GATE_SCHEMA,
    RESOLUTION_TOOL_NAME,
    TOOL_NAME,
)


def register(ctx: Any) -> None:
    config = load_plugin_config()
    store = ReceiptStore.from_path(config.receipt_path)

    def _handle_advisor_audit(args: dict[str, Any], **kw: Any) -> str:
        extra = dict(kw)
        effective_session = str(extra.pop("session_id", "") or extra.get("task_id") or "")
        return advisor_audit_handler(
            args,
            ctx=ctx,
            store=store,
            config=config,
            session_id=effective_session,
            **extra,
        )

    ctx.register_tool(
        name=TOOL_NAME,
        toolset="advisor_gate",
        schema=ADVISOR_AUDIT_SCHEMA,
        handler=_handle_advisor_audit,
        description="Run review-only Advisor Gate audit.",
    )
    ctx.register_tool(
        name=RESOLUTION_TOOL_NAME,
        toolset="advisor_gate",
        schema=ADVISOR_RESOLUTION_GATE_SCHEMA,
        handler=lambda args, **kw: advisor_resolution_gate_handler(
            args,
            store=store,
            config=config,
            session_id=str(kw.get("session_id") or kw.get("task_id") or ""),
        ),
        description="Record Commander resolution of Advisor findings.",
    )

    ctx.register_hook("subagent_start", lambda **kw: on_subagent_start(store, **kw))
    ctx.register_hook("subagent_stop", lambda **kw: on_subagent_stop(store, **kw))
    ctx.register_hook("pre_tool_call", lambda **kw: on_pre_tool_call(store, config, **kw))
    ctx.register_hook("post_tool_call", lambda **kw: on_post_tool_call(store, **kw))
    ctx.register_hook(
        "transform_llm_output",
        lambda **kw: on_transform_llm_output(store, config, **kw),
    )
    ctx.register_hook("pre_verify", lambda **kw: on_pre_verify(store, config, **kw))
