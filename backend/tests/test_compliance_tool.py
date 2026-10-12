"""End-to-end: agent should call the compliance tool on a flagged JD (spec 20B).

Spins up a ClaudeSDKClient with jd scenario, asks it to check a known-bad
JD, and prints the tool calls + final text. Verifies the agent actually
uses the tool rather than improvising.
"""
import asyncio
import json
import sys
from pathlib import Path

# Reconfigure stdout to UTF-8 *before* anything else — agent output contains
# characters (⚠, etc.) that the Windows GBK default codec can't encode.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from app.agent_options import build_options
from app.event_bus import EventBus

BAD_JD = (
    "请帮我检查这段 JD 的合规性：\n"
    "招聘后端工程师，限男性，35 岁以下，985 全日制本科，"
    "本地户口优先，形象气质佳，身高 170cm 以上。"
)


def _extract_risk(snippet: str) -> str | None:
    """Pull `risk_level` out of a tool result snippet.

    The SDK returns `b.content` as a Python list of content blocks; its
    `str()` is a Python repr (single quotes), not strict JSON. We first
    try strict JSON, then fall back to a substring scan for the
    `"risk_level": "high"` field — the latter is what actually matches
    against the SDK's repr output.
    """
    # Strict path: tool result is a JSON list with a `text` block.
    try:
        parsed = json.loads(snippet)
        if isinstance(parsed, list) and parsed:
            first = parsed[0]
            inner = first.get("text") or first.get("json")
            if isinstance(inner, str):
                parsed = json.loads(inner)
            elif isinstance(inner, dict):
                parsed = inner
        if isinstance(parsed, dict) and "risk_level" in parsed:
            return parsed["risk_level"]
    except Exception:
        pass

    # Fallback: scan for the field directly in the (possibly repr'd) text.
    if '"risk_level"' in snippet:
        i = snippet.find('"risk_level"')
        tail = snippet[i:i + 80]
        for needle in ('"high"', '"medium"', '"low"', '"none"'):
            if needle in tail:
                return needle.strip('"')
    return None


async def main() -> int:
    bus = EventBus()
    opts = build_options(
        "compliance_test", bus, prompt_override=None, scenario="jd",
    )
    tool_called = False
    risk_seen = None
    log_path = Path(__file__).resolve().parent / "compliance_tool_run.log"
    log = log_path.open("w", encoding="utf-8")

    def emit(s: str) -> None:
        print(s)
        log.write(s + "\n")

    try:
        async with ClaudeSDKClient(opts) as client:
            await client.query(BAD_JD)
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for b in msg.content:
                        if isinstance(b, TextBlock):
                            emit(f"[TEXT] {b.text[:400]}")
                        elif isinstance(b, ToolUseBlock):
                            emit(f"[TOOL] {b.name}: {json.dumps(b.input, ensure_ascii=False)}")
                            if b.name == "mcp__compliance_server__check_jd_compliance":
                                tool_called = True
                elif isinstance(msg, UserMessage):
                    for b in msg.content:
                        if isinstance(b, ToolResultBlock):
                            snippet = str(b.content)
                            emit(f"[RESULT] {snippet[:800]}")
                            risk_seen = _extract_risk(snippet)

        emit("")
        emit(f"tool_called={tool_called} risk_level={risk_seen}")
        if not tool_called:
            emit("FAIL: agent did not invoke check_jd_compliance")
            return 1
        if risk_seen != "high":
            emit(f"FAIL: expected risk_level=high, got {risk_seen}")
            return 1
        emit("=== compliance tool PASS ===")
        emit(f"(full log: {log_path})")
        return 0
    finally:
        log.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
