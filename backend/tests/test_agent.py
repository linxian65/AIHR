"""Smoke test: Claude Agent SDK + MiniMax-M3, two-round conversation."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    UserMessage,
    SystemMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    StreamEvent,
)

from app.config import MINIMAX_BASE_URL, MINIMAX_API_KEY, MINIMAX_MODEL


def make_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        env={
            "ANTHROPIC_BASE_URL": MINIMAX_BASE_URL,
            "ANTHROPIC_API_KEY": MINIMAX_API_KEY,
            "ANTHROPIC_MODEL": MINIMAX_MODEL,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": MINIMAX_MODEL,
        },
        system_prompt="你是一个测试助手，用中文回复。需要查看文件时使用工具。",
        allowed_tools=["Read", "Glob"],
        include_partial_messages=True,
        max_turns=5,
    )


async def drain(client: ClaudeSDKClient, label: str) -> None:
    print(f"--- {label}: receiving ---")
    async for msg in client.receive_response():
        print(f"[MSG TYPE] {type(msg).__name__}")
        if isinstance(msg, StreamEvent):
            ev = msg.event or {}
            delta = ev.get("delta") or {}
            print(f"  [STREAM] event.type={ev.get('type')} delta_type={delta.get('type')}")
        elif isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(f"  [TEXT] {block.text}")
                elif isinstance(block, ToolUseBlock):
                    print(f"  [TOOL_USE] id={block.id} name={block.name} input={block.input}")
        elif isinstance(msg, UserMessage):
            content = msg.content
            if isinstance(content, str):
                continue
            for block in content or []:
                if isinstance(block, ToolResultBlock):
                    print(
                        f"  [TOOL_RESULT] id={block.tool_use_id} "
                        f"is_error={block.is_error} content={str(block.content)[:200]}"
                    )
        elif isinstance(msg, SystemMessage):
            print(f"  [SYSTEM] subtype={msg.subtype}")
        elif isinstance(msg, ResultMessage):
            print(f"  [RESULT] subtype={msg.subtype} cost={getattr(msg, 'total_cost_usd', None)}")


async def main() -> None:
    options = make_options()
    async with ClaudeSDKClient(options) as client:
        await client.query("列出当前目录下的文件")
        await drain(client, "ROUND 1")
        print("=== ROUND 1 DONE ===\n")

        await client.query("刚才你看到了哪些文件？只列文件名。")
        await drain(client, "ROUND 2")
        print("=== ROUND 2 DONE ===")


if __name__ == "__main__":
    asyncio.run(main())
