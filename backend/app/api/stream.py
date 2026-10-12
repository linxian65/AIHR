"""GET /api/sessions/{sid}/stream — Server-Sent Events for live agent output."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from sse_starlette import EventSourceResponse

router = APIRouter()


@router.get("/{session_id}/stream")
async def stream(session_id: str, request: Request):
    bus = request.app.state.event_bus
    queue = bus.subscribe(session_id)

    async def gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield {
                        "event": ev["event"],
                        "data": json.dumps(ev["data"], ensure_ascii=False),
                    }
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            bus.unsubscribe(session_id, queue)

    return EventSourceResponse(gen())
