"""Per-session ClaudeSDKClient pool.

Each session_id maps to a long-lived ClaudeSDKClient. Creation and
disconnect are serialized by an asyncio.Lock keyed on session_id so
two concurrent HTTP requests cannot race on the same session.
"""
from __future__ import annotations

import asyncio

from claude_agent_sdk import ClaudeSDKClient

from app.agent_options import build_options
from app.event_bus import EventBus
from app.session_store import SessionStore


class SessionManager:
    def __init__(self, event_bus: EventBus, session_store: SessionStore) -> None:
        self.event_bus = event_bus
        self.session_store = session_store
        self._clients: dict[str, ClaudeSDKClient] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._active_turns: set[str] = set()
        self._turn_lock = asyncio.Lock()

    def _lock(self, sid: str) -> asyncio.Lock:
        return self._locks.setdefault(sid, asyncio.Lock())

    async def get_or_create(self, session_id: str) -> ClaudeSDKClient:
        async with self._lock(session_id):
            if session_id not in self._clients:
                scenario = await self.session_store.get_scenario(session_id)
                options = build_options(session_id, self.event_bus, scenario=scenario)
                client = ClaudeSDKClient(options)
                await client.connect()
                self._clients[session_id] = client
            return self._clients[session_id]

    async def close(self, session_id: str) -> None:
        async with self._lock(session_id):
            client = self._clients.pop(session_id, None)
            if client is not None:
                try:
                    await client.disconnect()
                except Exception as e:
                    print(f"[session_manager] disconnect error: {e}")

    async def close_all(self) -> None:
        for sid in list(self._clients.keys()):
            await self.close(sid)

    async def try_begin_turn(self, session_id: str) -> bool:
        async with self._turn_lock:
            if session_id in self._active_turns:
                return False
            self._active_turns.add(session_id)
            return True

    async def end_turn(self, session_id: str) -> None:
        async with self._turn_lock:
            self._active_turns.discard(session_id)

    async def is_turn_active(self, session_id: str) -> bool:
        async with self._turn_lock:
            return session_id in self._active_turns
