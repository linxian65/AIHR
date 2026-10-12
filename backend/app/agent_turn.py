"""Run one user turn against a session, translating SDK messages to EventBus events."""
from __future__ import annotations

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    StreamEvent,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from app.event_bus import EventBus
from app.session_manager import SessionManager
from app.session_store import SessionStore


async def run_agent_turn(
    session_id: str,
    content: str,
    session_manager: SessionManager,
    event_bus: EventBus,
    session_store: SessionStore,
) -> None:
    try:
        await session_store.upsert(session_id, is_new_message=True)
        await session_store.set_title_if_default(session_id, content)

        client = await session_manager.get_or_create(session_id)
        await client.query(content)
        async for msg in client.receive_response():
            await _translate_and_publish(session_id, msg, event_bus)
    except Exception as e:
        await event_bus.publish(session_id, {
            "event": "error",
            "data": {"message": str(e), "type": type(e).__name__},
        })
    finally:
        await event_bus.publish(session_id, {"event": "done", "data": {}})


async def _translate_and_publish(session_id: str, msg, event_bus: EventBus) -> None:
    if isinstance(msg, StreamEvent):
        ev = msg.event
        if ev.get("type") == "content_block_delta":
            delta = ev.get("delta", {})
            dt = delta.get("type")
            if dt == "text_delta":
                await event_bus.publish(session_id, {
                    "event": "message_delta",
                    "data": {"text": delta.get("text", "")},
                })
            elif dt == "thinking_delta":
                await event_bus.publish(session_id, {
                    "event": "thinking_delta",
                    "data": {"text": delta.get("thinking", "")},
                })
    elif isinstance(msg, AssistantMessage):
        for block in msg.content:
            if isinstance(block, ToolUseBlock):
                await event_bus.publish(session_id, {
                    "event": "tool_use_start",
                    "data": {
                        "tool_use_id": block.id,
                        "name": block.name,
                        "input": block.input,
                    },
                })
    elif isinstance(msg, UserMessage):
        for block in msg.content:
            if isinstance(block, ToolResultBlock):
                await event_bus.publish(session_id, {
                    "event": "tool_use_result",
                    "data": {
                        "tool_use_id": block.tool_use_id,
                        "success": block.is_error is not True,
                        "result": str(block.content)[:500],
                    },
                })
    elif isinstance(msg, ResultMessage):
        await event_bus.publish(session_id, {
            "event": "result",
            "data": {
                "subtype": msg.subtype,
                "cost_usd": getattr(msg, "total_cost_usd", None),
            },
        })
