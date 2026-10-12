"""FastAPI entrypoint for HR Recruit Agent backend."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import approvals, files, history, sessions, sessions_meta, stream
from app.db import init_db, close_db
from app.event_bus import EventBus
from app.migrate_json import run_once as migrate_json
from app.repositories import approvals_repo
from app.session_manager import SessionManager
from app.session_store import SessionStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await migrate_json()
    await approvals_repo.expire_stale(0)
    bus = EventBus()
    store = SessionStore()
    app.state.event_bus = bus
    app.state.session_store = store
    app.state.session_manager = SessionManager(bus, store)
    yield
    await app.state.session_manager.close_all()
    await close_db()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(sessions_meta.router, prefix="/api/sessions", tags=["sessions_meta"])
app.include_router(stream.router, prefix="/api/sessions", tags=["stream"])
app.include_router(approvals.router, prefix="/api/sessions", tags=["approvals"])
app.include_router(history.router, prefix="/api/sessions", tags=["history"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
