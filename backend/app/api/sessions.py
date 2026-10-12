"""POST /api/sessions/{sid}/messages — fire-and-forget turn dispatch."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.agent_turn import run_agent_turn

router = APIRouter()


class SendMessageRequest(BaseModel):
    content: str


@router.post("/{session_id}/messages")
async def send_message(session_id: str, body: SendMessageRequest, request: Request):
    manager = request.app.state.session_manager
    bus = request.app.state.event_bus
    store = request.app.state.session_store
    asyncio.create_task(run_agent_turn(session_id, body.content, manager, bus, store))
    return JSONResponse(
        {"accepted": True, "session_id": session_id}, status_code=202
    )
