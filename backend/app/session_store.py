"""JSON-file backed session metadata store.

Stores session id, title, createdAt, lastActiveAt in a single JSON file at
backend/data/sessions.json. No database, no message history. Per spec 13A.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import WORKSPACE_DIR
from app.scenarios import DEFAULT_SCENARIO

DATA_DIR = Path(WORKSPACE_DIR).parent / "data"
STORE_FILE = DATA_DIR / "sessions.json"

_DEFAULT_TITLE = "新会话"


class SessionStore:
    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if STORE_FILE.exists():
            try:
                self._data = json.loads(STORE_FILE.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[session_store] load failed: {e}")
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        STORE_FILE.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    async def upsert(
        self,
        session_id: str,
        title: Optional[str] = None,
        scenario: Optional[str] = None,
        is_new_message: bool = False,
    ) -> dict:
        async with self._lock:
            now = self._now()
            existing = self._data.get(session_id)

            if existing is None:
                self._data[session_id] = {
                    "id": session_id,
                    "title": title or _DEFAULT_TITLE,
                    "scenario": scenario or DEFAULT_SCENARIO,
                    "createdAt": now,
                    "lastActiveAt": now,
                }
            else:
                existing["lastActiveAt"] = now
                if title:
                    existing["title"] = title
                if scenario:
                    existing["scenario"] = scenario

            self._save()
            return dict(self._data[session_id])

    async def set_scenario(self, session_id: str, scenario: str) -> Optional[dict]:
        async with self._lock:
            entry = self._data.get(session_id)
            if entry is None:
                return None
            entry["scenario"] = scenario
            self._save()
            return dict(entry)

    async def get_scenario(self, session_id: str) -> str:
        async with self._lock:
            entry = self._data.get(session_id)
            return (entry or {}).get("scenario", DEFAULT_SCENARIO)

    async def set_title_if_default(self, session_id: str, message: str) -> None:
        async with self._lock:
            entry = self._data.get(session_id)
            if entry is None:
                return
            if entry.get("title") not in (None, "", _DEFAULT_TITLE):
                return
            first_line = message.strip().split("\n")[0][:30]
            if first_line:
                entry["title"] = first_line
                self._save()

    async def list(self) -> list[dict]:
        async with self._lock:
            items = list(self._data.values())
            items.sort(key=lambda x: x.get("lastActiveAt", ""), reverse=True)
            return [dict(x) for x in items]

    async def get(self, session_id: str) -> Optional[dict]:
        async with self._lock:
            entry = self._data.get(session_id)
            return dict(entry) if entry else None

    async def delete(self, session_id: str) -> bool:
        async with self._lock:
            if session_id in self._data:
                del self._data[session_id]
                self._save()
                return True
            return False

    async def rename(self, session_id: str, new_title: str) -> Optional[dict]:
        async with self._lock:
            entry = self._data.get(session_id)
            if entry is None:
                return None
            entry["title"] = new_title.strip()[:60] or "未命名"
            self._save()
            return dict(entry)
