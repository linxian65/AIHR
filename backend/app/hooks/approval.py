"""Approval gate: scrub -> approve -> audit pipeline.

Wired into ClaudeAgentOptions.can_use_tool. v2 uses an EventBus for
async approval round-trips and accepts session_id via closure.
"""
from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any

from claude_agent_sdk import (
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

from app.event_bus import EventBus
from app.hooks.pii import (
    make_audit_record,
    scan_pii_in_input,
    scrub_tool_input,
    write_audit,
)

DANGEROUS_PATTERNS = [
    re.compile(r"mcp__.*__send_.*"),
    re.compile(r"mcp__.*__notify_.*"),
    re.compile(r"mcp__.*__email_.*"),
    re.compile(r"mcp__ats_server__.*"),
]


def is_dangerous(tool_name: str) -> bool:
    return any(p.match(tool_name) for p in DANGEROUS_PATTERNS)


_pending: dict[str, dict[str, asyncio.Future]] = {}


def register_approval(session_id: str, approval_id: str) -> asyncio.Future:
    fut = asyncio.get_running_loop().create_future()
    _pending.setdefault(session_id, {})[approval_id] = fut
    return fut


def resolve_approval(
    session_id: str,
    approval_id: str,
    approved: bool,
    reason: str | None = None,
) -> bool:
    fut = _pending.get(session_id, {}).pop(approval_id, None)
    if fut is None or fut.done():
        return False
    fut.set_result({"approved": approved, "reason": reason})
    return True


def list_pending(session_id: str) -> list[str]:
    return list(_pending.get(session_id, {}).keys())


def make_can_use_tool(session_id: str, event_bus: EventBus):
    async def can_use_tool(
        tool_name: str,
        input_data: dict,
        context: ToolPermissionContext,
    ) -> Any:
        print(f"\n[can_use_tool] session={session_id} tool={tool_name}")

        # Stage 1: scrub (only mutates Write/Edit) and scan (all tools)
        scrubbed_input, _ = scrub_tool_input(tool_name, input_data)
        pii_hits = scan_pii_in_input(tool_name, scrubbed_input)
        if any(pii_hits.values()):
            print(f"[can_use_tool] PII hits: {pii_hits}")

        # Stage 2: approval
        if is_dangerous(tool_name):
            approval_id = f"apr_{uuid.uuid4().hex[:10]}"
            future = register_approval(session_id, approval_id)
            await event_bus.publish(
                session_id,
                {
                    "event": "approval_required",
                    "data": {
                        "approval_id": approval_id,
                        "tool_name": tool_name,
                        "input": scrubbed_input,
                    },
                },
            )
            print(f"[can_use_tool] waiting approval {approval_id} ...")
            decision = await future
            approved = decision["approved"]
            reason = decision.get("reason")
            print(f"[can_use_tool] approval result: approved={approved}")
            if approved:
                result = (
                    PermissionResultAllow(updated_input=scrubbed_input)
                    if scrubbed_input is not input_data
                    else PermissionResultAllow()
                )
                audit_decision, audit_reason = "allow", None
            else:
                result = PermissionResultDeny(
                    message=reason or "用户拒绝此操作，请告知用户或尝试其他方案。"
                )
                audit_decision = "deny"
                audit_reason = reason or "user_rejected"
        else:
            result = (
                PermissionResultAllow(updated_input=scrubbed_input)
                if scrubbed_input is not input_data
                else PermissionResultAllow()
            )
            audit_decision, audit_reason = "allow", None

        # Stage 3: audit
        write_audit(
            make_audit_record(
                session_id=session_id,
                tool_name=tool_name,
                input_data=scrubbed_input,
                decision=audit_decision,
                reason=audit_reason,
                pii_hits=pii_hits,
            )
        )
        return result

    return can_use_tool
