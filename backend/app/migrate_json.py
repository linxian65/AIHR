"""One-shot migration: data/sessions.json -> SQLite (spec 16A).

Reads the legacy JSON store, upserts each entry into the sessions table,
then renames the JSON file to .bak so subsequent starts are no-ops.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.config import WORKSPACE_DIR
from app.repositories import sessions_repo

OLD = Path(WORKSPACE_DIR).parent / "data" / "sessions.json"


async def run_once() -> None:
    if not OLD.exists():
        return
    try:
        data = json.loads(OLD.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[migrate] 读取失败: {e}")
        return
    count = 0
    for sid, meta in data.items():
        existing = await sessions_repo.get(sid)
        if existing:
            continue
        await sessions_repo.upsert(
            sid,
            title=meta.get("title"),
            created_at=meta.get("createdAt"),
            last_active_at=meta.get("lastActiveAt"),
        )
        if meta.get("scenario"):
            await sessions_repo.set_scenario(sid, meta["scenario"])
        count += 1
    if count:
        bak = OLD.with_suffix(".json.bak")
        OLD.rename(bak)
        print(f"[migrate] 已迁移 {count} 条会话到 SQLite，原文件改名为 {bak.name}")