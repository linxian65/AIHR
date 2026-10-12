"""CRUD endpoints for session metadata + scenarios (spec 13A + 14A).

Mounted at /api/sessions. Does not conflict with sessions.py's
/{session_id}/messages (different path).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.scenarios import list_scenarios

router = APIRouter()


class CreateRequest(BaseModel):
    session_id: str
    title: str | None = None
    scenario: str | None = None


class PatchRequest(BaseModel):
    title: str | None = None
    scenario: str | None = None


@router.get("/scenarios")
async def get_scenarios():
    return {"scenarios": list_scenarios()}


@router.get("")
async def list_sessions(request: Request):
    store = request.app.state.session_store
    return {"sessions": await store.list()}


@router.post("")
async def create_session(body: CreateRequest, request: Request):
    store = request.app.state.session_store
    meta = await store.upsert(body.session_id, title=body.title, scenario=body.scenario)
    return meta


@router.get("/{session_id}")
async def get_session(session_id: str, request: Request):
    store = request.app.state.session_store
    meta = await store.get(session_id)
    if not meta:
        raise HTTPException(404, "会话不存在")
    return meta


@router.patch("/{session_id}")
async def patch_session(session_id: str, body: PatchRequest, request: Request):
    store = request.app.state.session_store
    manager = request.app.state.session_manager
    changed_scenario = False

    if body.title is not None:
        meta = await store.rename(session_id, body.title)
        if not meta:
            raise HTTPException(404, "会话不存在")

    if body.scenario is not None:
        meta = await store.set_scenario(session_id, body.scenario)
        if not meta:
            raise HTTPException(404, "会话不存在")
        changed_scenario = True

    if changed_scenario:
        await manager.close(session_id)

    return await store.get(session_id)


@router.delete("/{session_id}")
async def delete_session(session_id: str, request: Request):
    store = request.app.state.session_store
    manager = request.app.state.session_manager
    await manager.close(session_id)
    ok = await store.delete(session_id)
    return {"deleted": ok}
