"""Approval REST endpoints — list pending and resolve decisions.

Spec 16B-2: pending approvals are persisted in SQLite; on list we age
out anything past 5 minutes (in-memory future is surely gone by then);
on decide we update the row first then wake the in-process future.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.hooks.approval import resolve_approval
from app.repositories import approvals_repo

router = APIRouter()


class DecisionRequest(BaseModel):
    approved: bool
    reason: str | None = None


@router.get("/{session_id}/approvals")
async def list_approvals(session_id: str, request: Request):
    # Run the 5-minute staleness sweep before reporting — anything older
    # was created in a previous process lifetime and its future is dead.
    await approvals_repo.expire_stale()
    items = await approvals_repo.list_pending(session_id)
    return {"pending": items}


@router.post("/{session_id}/approvals/{approval_id}")
async def decide(
    session_id: str,
    approval_id: str,
    body: DecisionRequest,
    request: Request,
):
    status = "approved" if body.approved else "rejected"
    await approvals_repo.decide(approval_id, status, body.reason)
    ok = resolve_approval(session_id, approval_id, body.approved, body.reason)
    return {"ok": ok, "approval_id": approval_id, "approved": body.approved}