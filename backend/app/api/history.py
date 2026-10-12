"""GET /api/sessions/{sid}/history — paginated turns (oldest -> newest).

Spec 16B-1. The repo returns newest-first, so we reverse for clients.
`before` is a cursor on turn_index; clients pass the smallest turn_index
they already have to fetch older pages.
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.repositories import turns_repo

router = APIRouter()


@router.get("/{session_id}/history")
async def get_history(
    session_id: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    before: int | None = Query(None, ge=1),
):
    turns = await turns_repo.history(session_id, limit=limit, before_turn=before)
    total = await turns_repo.count(session_id)
    total_cost = await turns_repo.total_cost(session_id)

    # has_more: there's at least one older turn beyond the oldest we returned
    has_more = bool(turns) and turns[-1]["turn_index"] > 1

    return {
        "turns": list(reversed(turns)),
        "total": total,
        "has_more": has_more,
        "total_cost": total_cost,
    }