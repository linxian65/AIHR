"""POST /api/sessions/{sid}/messages — fire-and-forget turn dispatch.

Spec 16B-1: writes a pending turn row first, then schedules the agent
run in the background. The handler returns 202 with the assigned
turn_index so the client can correlate later history loads.

Spec 17A: a per-session turn-lock rejects concurrent posts with 409.

Spec 17B: a per-session cost cap rejects posts with 402.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.agent_turn import run_agent_turn
from app.batch_screen import run_batch_screen
from app.config import SESSION_COST_LIMIT_USD
from app.repositories import turns_repo

router = APIRouter()


class SendMessageRequest(BaseModel):
    content: str


class BatchScreenRequest(BaseModel):
    jd_text: str
    resume_paths: list[str]


@router.post("/{session_id}/messages")
async def send_message(session_id: str, body: SendMessageRequest, request: Request):
    manager = request.app.state.session_manager
    bus = request.app.state.event_bus
    store = request.app.state.session_store

    # 17B: cumulative cost cap. Checked before acquiring the turn slot
    # so a refused request doesn't lock the session.
    current_cost = await turns_repo.total_cost(session_id)
    if current_cost >= SESSION_COST_LIMIT_USD:
        raise HTTPException(
            402,
            f"该会话累计成本 ${current_cost:.2f} 已达上限 "
            f"${SESSION_COST_LIMIT_USD:.2f}，请新建会话或联系管理员调整上限",
        )

    # 17A: turn-slot lock.
    ok = await manager.try_begin_turn(session_id)
    if not ok:
        raise HTTPException(409, "该会话上一条消息还在处理中，请等待完成")

    try:
        turn_index = await turns_repo.create_pending(session_id, body.content)
    except Exception:
        # 占位失败要释放槽位，否则会话永久卡死
        await manager.end_turn(session_id)
        raise

    asyncio.create_task(
        run_agent_turn(session_id, body.content, turn_index, manager, bus, store)
    )
    return JSONResponse(
        {"accepted": True, "session_id": session_id, "turn_index": turn_index},
        status_code=202,
    )


@router.post("/{session_id}/batch-screen")
async def batch_screen(
    session_id: str, body: BatchScreenRequest, request: Request,
):
    if not body.resume_paths:
        raise HTTPException(400, "resume_paths 不能为空")
    if len(body.resume_paths) > 50:
        raise HTTPException(400, "单次批量评估上限 50 份")

    manager = request.app.state.session_manager
    bus = request.app.state.event_bus

    # Reuse the same turn-slot lock so a chat message and a batch can't
    # fight over the same session's agent client.
    ok = await manager.try_begin_turn(session_id)
    if not ok:
        raise HTTPException(409, "该会话有任务正在进行中")

    try:
        turn_index = await turns_repo.create_pending(
            session_id, f"[批量评估] {len(body.resume_paths)} 份简历",
        )
    except Exception:
        await manager.end_turn(session_id)
        raise

    captured: list[dict] = []

    async def _capture(event: str, data: dict) -> None:
        captured.append({"event": event, "data": data})

    async def _run() -> None:
        final_status = "ok"
        try:
            await run_batch_screen(
                session_id, body.jd_text, body.resume_paths,
                manager, bus, on_event=_capture,
            )
        except Exception as e:
            final_status = "error"
            await bus.publish(session_id, {
                "event": "error",
                "data": {"message": str(e), "type": type(e).__name__},
            })
        finally:
            # `done` for SSE consumers — emit after we've stopped capturing
            # so the placeholder isn't stored as a turn event.
            await bus.publish(session_id, {"event": "done", "data": {}})
            try:
                await turns_repo.finalize(
                    session_id, turn_index, captured,
                    status=final_status, cost_usd=None,
                )
            except Exception as e:
                print(f"[batch_screen] finalize failed: {e}")

    asyncio.create_task(_run())

    return JSONResponse(
        {"accepted": True, "turn_index": turn_index, "total": len(body.resume_paths)},
        status_code=202,
    )