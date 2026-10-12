"""SQLite connection holder (spec 16A).

Single shared aiosqlite connection across the app, opened in main.py lifespan.
WAL mode + foreign keys ON. Schema is applied at init.
"""
from __future__ import annotations

from pathlib import Path

import aiosqlite

from app.config import WORKSPACE_DIR

DB_PATH = Path(WORKSPACE_DIR).parent / "data" / "agent.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

_conn: aiosqlite.Connection | None = None


async def init_db() -> None:
    global _conn
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _conn = await aiosqlite.connect(DB_PATH)
    _conn.row_factory = aiosqlite.Row
    await _conn.execute("PRAGMA journal_mode=WAL")
    await _conn.execute("PRAGMA foreign_keys=ON")
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    await _conn.executescript(schema)
    await _conn.commit()


async def close_db() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


def get_conn() -> aiosqlite.Connection:
    if _conn is None:
        raise RuntimeError("数据库尚未初始化，检查 main.py lifespan")
    return _conn