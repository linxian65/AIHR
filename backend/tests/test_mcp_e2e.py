"""End-to-end test: agent_options + resume MCP, two rounds incl. Bash denial."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claude_agent_sdk import (
    ClaudeSDKClient,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    ResultMessage,
    StreamEvent,
)

from app.agent_options import build_options


async def drain(client: ClaudeSDKClient, label: str) -> None:
    print(f"--- {label}: receiving ---")
    async for msg in client.receive_response():
        tname = type(msg).__name__
        if tname == "StreamEvent":
            ev = msg.event or {}
            delta = ev.get("delta") or {}
            et = ev.get("type")
            dt = delta.get("type")
            if et in ("content_block_delta",) and dt in ("text_delta", "input_json_delta"):
                pass
            continue
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
    options = build_options()
    async with ClaudeSDKClient(options) as client:
        await client.query("请解析 /tmp/test_resume.pdf 的简历，然后给出评分")
        await drain(client, "ROUND 1")
        print("=== ROUND 1 DONE ===\n")

        await client.query("请用 Bash 执行 ls")
        await drain(client, "ROUND 2")
        print("=== ROUND 2 DONE ===\n")

    print("=== E2E DONE ===")


if __name__ == "__main__":
    asyncio.run(main())
