"""Approval e2e v2: same y/n via stdin, but routed through EventBus."""
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

TEST_PROMPT = (
    "你是一个工具执行助手。用户要求调用什么工具，你就调用什么工具，不做业务判断。"
)
SESSION_ID = "approval_stdin"


async def subscriber_stdin_loop(bus: EventBus, session_id: str) -> None:
    q = bus.subscribe(session_id)
    while True:
        ev = await q.get()
        if ev.get("event") != "approval_required":
            continue
        data = ev["data"]
        print(f"\n{'=' * 60}")
        print(f"⚠️  需审批的工具调用")
        print(f"工具: {data['tool_name']}")
        print(f"参数: {data['input']}")
        print(f"{'=' * 60}")
        answer = input("批准? (y/n): ").strip().lower()
        approved = answer == "y"
        ok = resolve_approval(session_id, data["approval_id"], approved=approved)
        print(f"[stdin-subscriber] resolved approved={approved}: {ok}")


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
    sub = asyncio.create_task(subscriber_stdin_loop(bus, SESSION_ID))
    try:
        options = build_options(
            session_id=SESSION_ID,
            event_bus=bus,
            prompt_override=TEST_PROMPT,
        )
        async with ClaudeSDKClient(options) as client:
            await client.query(
                "请调用 send_email 工具，参数：to=zhangsan@example.com, "
                "subject='面试邀请', body='请于周五下午 2 点参加面试'。"
                "不要做其他事。"
            )
            await drain(client)
        print("=== APPROVAL E2E DONE ===")
    finally:
        sub.cancel()
        try:
            await sub
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
