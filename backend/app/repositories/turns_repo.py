"""SQLite-backed turns repository (spec 16A).

Each row = one user turn (a complete agent run including streamed events).
events_json holds the full SSE event log replayed on session reload.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app.db import get_conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_pending(session_id: str, user_content: str) -> int:
    """Insert a user-only placeholder turn. Returns the assigned turn_index."""
    conn = get_conn()
    row = await (await conn.execute(
        "SELECT COALESCE(MAX(turn_index), 0) + 1 AS next FROM turns "
        "WHERE session_id = ?",
        (session_id,),
    )).fetchone()
    next_idx = row["next"]
    await conn.execute(
        "INSERT INTO turns (session_id, turn_index, user_content, status, created_at) "
        "VALUES (?, ?, ?, 'pending', ?)",
        (session_id, next_idx, user_content, _now()),
    )
    await conn.commit()
    return next_idx


async def finalize(session_id: str, turn_index: int, events: list[dict],
                   status: str = "ok", cost_usd: float | None = None) -> None:
    conn = get_conn()
    await conn.execute(
        "UPDATE turns SET events_json = ?, status = ?, cost_usd = ? "
        "WHERE session_id = ? AND turn_index = ?",
        (json.dumps(events, ensure_ascii=False), status, cost_usd,
         session_id, turn_index),
    )
    await conn.commit()


async def history(session_id: str, limit: int = 20,
                  before_turn: int | None = None) -> list[dict]:
    """Return turns newest-first; the caller reverses if it wants oldest-first."""
    conn = get_conn()
    if before_turn is not None:
        rows = await (await conn.execute(
            "SELECT * FROM turns WHERE session_id = ? AND turn_index < ? "
            "ORDER BY turn_index DESC LIMIT ?",
            (session_id, before_turn, limit),
        )).fetchall()
    else:
        rows = await (await conn.execute(
            "SELECT * FROM turns WHERE session_id = ? "
            "ORDER BY turn_index DESC LIMIT ?",
            (session_id, limit),
        )).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["events"] = json.loads(d.pop("events_json") or "[]")
        out.append(d)
    return out


async def count(session_id: str) -> int:
    conn = get_conn()
    row = await (await conn.execute(
        "SELECT COUNT(*) AS c FROM turns WHERE session_id = ?", (session_id,)
    )).fetchone()
    return row["c"]


async def total_cost(session_id: str) -> float:
    conn = get_conn()
    row = await (await conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM turns "
        "WHERE session_id = ?",
        (session_id,),
    )).fetchone()
    return float(row["total"] or 0.0)