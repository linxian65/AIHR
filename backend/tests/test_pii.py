"""PII scrubber e2e test: 4 queries covering phone/id/email and approval combo."""
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
SESSION_ID = "pii_test"


async def auto_approver(bus: EventBus, session_id: str) -> None:
    q = bus.subscribe(session_id)
    while True:
        ev = await q.get()
        if ev.get("event") == "approval_required":
            resolve_approval(session_id, ev["data"]["approval_id"], approved=True)


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
    sub = asyncio.create_task(auto_approver(bus, SESSION_ID))
    options = build_options(
        session_id=SESSION_ID,
        event_bus=bus,
        prompt_override=TEST_PROMPT,
    )
    async with ClaudeSDKClient(options) as client:
        for label, query in [
            (
                "Q1 phone",
                "请用 Write 工具把以下内容写入 /tmp/pii_test_1.txt：\n"
                "联系人张三，手机 13812345678，已确认面试。",
            ),
            (
                "Q2 id+email",
                "请用 Write 工具把以下内容写入 /tmp/pii_test_2.txt：\n"
                "候选人身份证 110101199001011234，邮箱 zhangsan@example.com。",
            ),
            (
                "Q3 no PII",
                "请用 Write 工具把以下内容写入 /tmp/pii_test_3.txt：\n"
                "这是一份测试文档，没有任何敏感信息。",
            ),
            (
                "Q4 approval+email+phone",
                "请调用 send_email 工具，参数：\n"
                " to=zhangsan@example.com,\n"
                " subject=面试邀请,\n"
                " body=请联系 13812345678 确认时间。",
            ),
        ]:
            print(f"\n========== {label} ==========")
            await client.query(query)
            await drain(client)
    print("\n=== PII E2E DONE ===")
    sub.cancel()
    try:
        await sub
    except asyncio.CancelledError:
        pass

    print("\n========== FILE CONTENTS ==========")
    for p in [
        "/tmp/pii_test_1.txt",
        "/tmp/pii_test_2.txt",
        "/tmp/pii_test_3.txt",
    ]:
        path = Path(p)
        if path.exists():
            print(f"\n--- {p} ---")
            print(path.read_text(encoding="utf-8"), end="")
        else:
            print(f"\n--- {p} (NOT FOUND) ---")

    print(f"\n\n========== AUDIT LOG ({AUDIT_LOG}) ==========")
    if AUDIT_LOG.exists():
        print(AUDIT_LOG.read_text(encoding="utf-8"), end="")
    else:
        print("(audit log not found)")


if __name__ == "__main__":
    asyncio.run(main())
