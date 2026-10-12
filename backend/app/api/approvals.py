"""Approval REST endpoints — list pending and resolve decisions."""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.hooks.approval import list_pending, resolve_approval

router = APIRouter()


class DecisionRequest(BaseModel):
    approved: bool
    reason: str | None = None


@router.get("/{session_id}/approvals")
async def list_approvals(session_id: str, request: Request):
    ids = list_pending(session_id)
    return {"pending": ids}


@router.post("/{session_id}/approvals/{approval_id}")
async def decide(
    session_id: str,
    approval_id: str,
    body: DecisionRequest,
    request: Request,
):
    ok = resolve_approval(session_id, approval_id, body.approved, body.reason)
    return {"ok": ok, "approval_id": approval_id, "approved": body.approved}
