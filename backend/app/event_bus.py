"""Per-session pub/sub for async events from agent to API layer."""
from __future__ import annotations

import asyncio
from collections import defaultdict

MAX_QUEUE = 256


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, session_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE)
        self._subscribers[session_id].append(q)
        return q

    async def publish(self, session_id: str, event: dict) -> None:
        for q in list(self._subscribers.get(session_id, [])):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:
                    pass

    def unsubscribe(self, session_id: str, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(session_id)
        if subs and q in subs:
            subs.remove(q)
            if not subs:
                self._subscribers.pop(session_id, None)
