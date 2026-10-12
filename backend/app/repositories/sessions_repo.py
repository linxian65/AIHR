"""SQLite-backed sessions repository (spec 16A).

Internal representation uses snake_case columns. The SessionStore layer
maps these to camelCase before returning to the rest of the app so the
public API stays unchanged.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.db import get_conn
from app.scenarios import DEFAULT_SCENARIO

_DEFAULT_TITLE = "新会话"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def upsert(session_id: str, title: str | None = None,
                 scenario: str | None = None,
                 created_at: str | None = None,
                 last_active_at: str | None = None) -> dict:
    conn = get_conn()
    now = _now()
    row = await (await conn.execute(
        "SELECT * FROM sessions WHERE id = ?", (session_id,)
    )).fetchone()
    if row is None:
        await conn.execute(
            "INSERT INTO sessions (id, title, scenario, created_at, last_active_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, title or _DEFAULT_TITLE, scenario or DEFAULT_SCENARIO,
             created_at or now, last_active_at or now),
        )
    else:
        sets = ["last_active_at = ?"]
        params = [now]
        if title:
            sets.append("title = ?")
            params.append(title)
        if scenario:
            sets.append("scenario = ?")
            params.append(scenario)
        params.append(session_id)
        await conn.execute(
            f"UPDATE sessions SET {', '.join(sets)} WHERE id = ?", params
        )
    await conn.commit()
    return await get(session_id)


async def get(session_id: str) -> Optional[dict]:
    conn = get_conn()
    row = await (await conn.execute(
        "SELECT * FROM sessions WHERE id = ?", (session_id,)
    )).fetchone()
    return dict(row) if row else None


async def list_all() -> list[dict]:
    conn = get_conn()
    rows = await (await conn.execute(
        "SELECT * FROM sessions ORDER BY last_active_at DESC"
    )).fetchall()
    return [dict(r) for r in rows]


async def set_title_if_default(session_id: str, message: str) -> None:
    conn = get_conn()
    row = await (await conn.execute(
        "SELECT title FROM sessions WHERE id = ?", (session_id,)
    )).fetchone()
    if row is None:
        return
    if row["title"] not in (None, "", _DEFAULT_TITLE):
        return
    first_line = message.strip().split("\n")[0][:30]
    if not first_line:
        return
    await conn.execute(
        "UPDATE sessions SET title = ? WHERE id = ?", (first_line, session_id)
    )
    await conn.commit()


async def rename(session_id: str, new_title: str) -> Optional[dict]:
    conn = get_conn()
    cleaned = new_title.strip()[:60] or "未命名"
    await conn.execute(
        "UPDATE sessions SET title = ? WHERE id = ?", (cleaned, session_id)
    )
    await conn.commit()
    return await get(session_id)


async def set_scenario(session_id: str, scenario: str) -> Optional[dict]:
    conn = get_conn()
    await conn.execute(
        "UPDATE sessions SET scenario = ? WHERE id = ?", (scenario, session_id)
    )
    await conn.commit()
    return await get(session_id)


async def get_scenario(session_id: str) -> str:
    s = await get(session_id)
    return s["scenario"] if s else DEFAULT_SCENARIO


async def delete(session_id: str) -> bool:
    conn = get_conn()
    cur = await conn.execute(
        "DELETE FROM sessions WHERE id = ?", (session_id,)
    )
    await conn.commit()
    return cur.rowcount > 0