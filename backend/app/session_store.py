"""Thin facade over sessions_repo (spec 16A).

The JSON file backend was replaced with SQLite in spec 16. To avoid
touching every caller, this class keeps the same async interface and
maps the snake_case rows from the repo to the camelCase dict shape the
rest of the app (and the frontend) expects.
"""
from __future__ import annotations

from typing import Optional

from app.repositories import sessions_repo

_SNAKE_TO_CAMEL = {
    "created_at": "createdAt",
    "last_active_at": "lastActiveAt",
}


def _row_to_meta(row: Optional[dict]) -> Optional[dict]:
    if row is None:
        return None
    return {_SNAKE_TO_CAMEL.get(k, k): v for k, v in row.items()}


class SessionStore:
    async def upsert(self, session_id, title=None, scenario=None,
                     is_new_message=False, created_at=None, last_active_at=None):
        return _row_to_meta(await sessions_repo.upsert(
            session_id, title, scenario, created_at, last_active_at
        ))

    async def set_scenario(self, session_id, scenario):
        return _row_to_meta(await sessions_repo.set_scenario(session_id, scenario))

    async def get_scenario(self, session_id):
        return await sessions_repo.get_scenario(session_id)

    async def set_title_if_default(self, session_id, message):
        return await sessions_repo.set_title_if_default(session_id, message)

    async def list(self):
        return [_row_to_meta(r) for r in (await sessions_repo.list_all()) if r is not None]

    async def get(self, session_id):
        return _row_to_meta(await sessions_repo.get(session_id))

    async def delete(self, session_id):
        return await sessions_repo.delete(session_id)

    async def rename(self, session_id, new_title):
        return _row_to_meta(await sessions_repo.rename(session_id, new_title))