"""Approval v2 e2e: EventBus + async future, no stdin.

Verifies:
- approval_required event is published on EventBus
- can_use_tool awaits the future without deadlock
- resolve_approval unblocks the tool
- audit log: pii_hits.phone == 1 but input_hash matches raw input
  (proves scan ran on all tools but scrub only on Write/Edit)
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claude_agent_sdk import (
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    ResultMessage,
    ClaudeSDKClient,
)

from app.agent_options import build_options
from app.event_bus import EventBus
from app.hooks.approval import resolve_approval
from app.hooks.pii import AUDIT_LOG

TEST_PROMPT = "你是一个工具执行助手，用户要求调用什么工具，你就调用什么工具。"
SESSION_ID = "test_s1"


async def subscriber_loop(bus: EventBus) -> None:
    q = bus.subscribe(SESSION_ID)
    print(f"[subscriber] listening on session={SESSION_ID}")
    while True:
        ev = await q.get()
        if ev.get("event") == "approval_required":
            data = ev["data"]
            print(f"[subscriber] APPROVAL_REQUIRED id={data['approval_id']}")
            print(f"[subscriber]   tool  = {data['tool_name']}")
            print(f"[subscriber]   input = {data['input']}")
            ok = resolve_approval(SESSION_ID, data["approval_id"], approved=True)
            print(f"[subscriber] resolved (approved=True): {ok}")
        else:
            print(f"[subscriber] event: {ev}")


async def drain(client: ClaudeSDKClient) -> None:
    async for msg in client.receive_response():
        tname = type(msg).__name__
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(f"  [TEXT] {block.text}")
                elif isinstance(block, ToolUseBlock):
                    print(f"  [TOOL_USE] id={block.id} name={block.name} input={block.input}")
        elif tname == "UserMessage":
            content = msg.content
            if isinstance(content, str):
                continue
            for block in content or []:
                if isinstance(block, ToolResultBlock):
                    print(
                        f"  [TOOL_RESULT] id={block.tool_use_id} "
                        f"is_error={block.is_error} content={str(block.content)[:200]}"
                    )
        elif isinstance(msg, ResultMessage):
            print(f"  [RESULT] subtype={msg.subtype} cost={getattr(msg, 'total_cost_usd', None)}")


async def main() -> None:
    bus = EventBus()
    sub = asyncio.create_task(subscriber_loop(bus))
    try:
        options = build_options(
            session_id=SESSION_ID,
            event_bus=bus,
            prompt_override=TEST_PROMPT,
        )
        async with ClaudeSDKClient(options) as client:
            await client.query(
                "请调用 send_email，"
                "to=a@b.com, subject=面试邀请, "
                "body=请联系 13812345678 确认时间。"
            )
            await drain(client)
        print("\n=== APPROVAL V2 DONE ===")
    finally:
        sub.cancel()
        try:
            await sub
        except asyncio.CancelledError:
            pass

    print(f"\n========== AUDIT LOG ({AUDIT_LOG}) ==========")
    if AUDIT_LOG.exists():
        print(AUDIT_LOG.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    asyncio.run(main())
