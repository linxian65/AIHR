"""SQLite-backed approvals repository (spec 16A).

Persists human-in-the-loop approval requests so a server restart doesn't
lose them. Pending rows older than the last server lifetime are marked
'exppired' on startup (in-memory futures are already gone by then).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app.db import get_conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create(approval_id: str, session_id: str, tool_name: str,
                 input_data: dict) -> dict:
    conn = get_conn()
    await conn.execute(
        "INSERT INTO approvals "
        "(id, session_id, tool_name, input_json, status, created_at) "
        "VALUES (?, ?, ?, ?, 'pending', ?)",
        (approval_id, session_id, tool_name,
         json.dumps(input_data, ensure_ascii=False), _now()),
    )
    await conn.commit()
    return await get(approval_id)


async def get(approval_id: str) -> dict | None:
    conn = get_conn()
    row = await (await conn.execute(
        "SELECT * FROM approvals WHERE id = ?", (approval_id,)
    )).fetchone()
    if not row:
        return None
    d = dict(row)
    d["input"] = json.loads(d.pop("input_json"))
    return d


async def decide(approval_id: str, status: str, reason: str | None = None,
                 decided_by: str = "hr_user") -> None:
    conn = get_conn()
    await conn.execute(
        "UPDATE approvals SET status = ?, reason = ?, decided_at = ?, decided_by = ? "
        "WHERE id = ? AND status = 'pending'",
        (status, reason, _now(), decided_by, approval_id),
    )
    await conn.commit()


async def list_pending(session_id: str) -> list[dict]:
    conn = get_conn()
    rows = await (await conn.execute(
        "SELECT * FROM approvals WHERE session_id = ? AND status = 'pending' "
        "ORDER BY created_at ASC",
        (session_id,),
    )).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["input"] = json.loads(d.pop("input_json"))
        out.append(d)
    return out


async def expire_stale(min_age_seconds: int = 300) -> None:
    """Mark still-pending rows older than min_age_seconds as expired.

    Called at startup with 0 (every pending row, since in-memory futures
    are dead) and during normal operation with the default 300s window
    to avoid killing approvals that are actively being awaited.
    """
    from datetime import timedelta

    cutoff = (
        datetime.now(timezone.utc) - timedelta(seconds=min_age_seconds)
    ).isoformat()
    conn = get_conn()
    await conn.execute(
        "UPDATE approvals SET status = 'expired' "
        "WHERE status = 'pending' AND created_at < ?",
        (cutoff,),
    )
    await conn.commit()