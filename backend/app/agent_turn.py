"""Run one user turn against a session, translating SDK messages to EventBus events.

Spec 16B-1: also accumulates the event stream and finalizes a row in the
turns table when the run ends (success or error).
"""
from __future__ import annotations

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    StreamEvent,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from app.event_bus import EventBus
from app.repositories import turns_repo
from app.session_manager import SessionManager
from app.session_store import SessionStore


async def run_agent_turn(
    session_id: str,
    content: str,
    turn_index: int,
    session_manager: SessionManager,
    event_bus: EventBus,
    session_store: SessionStore,
) -> None:
    events: list[dict] = []
    cost_usd: float | None = None
    final_status = "ok"

    async def emit(event: str, data: dict) -> None:
        nonlocal cost_usd
        events.append({"event": event, "data": data})
        if event == "result":
            cost_usd = data.get("cost_usd")
        await event_bus.publish(session_id, {"event": event, "data": data})

    try:
        await session_store.upsert(session_id, is_new_message=True)
        await session_store.set_title_if_default(session_id, content)

        client = await session_manager.get_or_create(session_id)
        await client.query(content)
        async for msg in client.receive_response():
            await _translate_and_publish(session_id, msg, emit)
    except Exception as e:
        final_status = "error"
        await emit("error", {"message": str(e), "type": type(e).__name__})
    finally:
        await emit("done", {})
        try:
            await turns_repo.finalize(
                session_id, turn_index, events,
                status=final_status, cost_usd=cost_usd,
            )
        except Exception as e:
            print(f"[agent_turn] finalize failed: {e}")
        await session_manager.end_turn(session_id)


async def _translate_and_publish(session_id: str, msg, emit) -> None:
    if isinstance(msg, StreamEvent):
        ev = msg.event
        if ev.get("type") == "content_block_delta":
            delta = ev.get("delta", {})
            dt = delta.get("type")
            if dt == "text_delta":
                await emit("message_delta", {"text": delta.get("text", "")})
            elif dt == "thinking_delta":
                await emit("thinking_delta", {"text": delta.get("thinking", "")})
    elif isinstance(msg, AssistantMessage):
        for block in msg.content:
            if isinstance(block, ToolUseBlock):
                await emit("tool_use_start", {
                    "tool_use_id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
    elif isinstance(msg, UserMessage):
        for block in msg.content:
            if isinstance(block, ToolResultBlock):
                await emit("tool_use_result", {
                    "tool_use_id": block.tool_use_id,
                    "success": block.is_error is not True,
                    "result": str(block.content)[:500],
                })
    elif isinstance(msg, ResultMessage):
        await emit("result", {
            "subtype": msg.subtype,
            "cost_usd": getattr(msg, "total_cost_usd", None),
        })