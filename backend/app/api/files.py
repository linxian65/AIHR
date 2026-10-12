"""Files API: tree + content + upload per session workspace. Path-traversal safe."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.config import WORKSPACE_DIR

router = APIRouter()

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
SAFE_NAME_RE = re.compile(r"[^\w一-鿿.\-]+")


def _session_root(session_id: str) -> Path:
    root = (Path(WORKSPACE_DIR) / session_id).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_path(session_id: str, rel: str) -> Path:
    """Resolve and check rel is inside session_root. Raises 400 on traversal."""
    root = _session_root(session_id)
    target = (root / rel).resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(400, "路径越界")
    return target


@router.get("/{session_id}/tree")
async def get_tree(session_id: str):
    root = _session_root(session_id)

    def walk(p: Path):
        if p.is_file():
            st = p.stat()
            return {
                "name": p.name,
                "path": str(p.relative_to(root)).replace("\\", "/"),
                "type": "file",
                "size": st.st_size,
                "mtime": st.st_mtime,
            }
        children = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
        return {
            "name": p.name or session_id,
            "path": str(p.relative_to(root)).replace("\\", "/"),
            "type": "dir",
            "children": [walk(c) for c in children if not c.name.startswith(".")],
        }

    return walk(root)


@router.get("/{session_id}/content")
async def get_content(session_id: str, path: str = Query(...)):
    target = _safe_path(session_id, path)
    if not target.is_file():
        raise HTTPException(404, "文件不存在")
    if target.stat().st_size > MAX_FILE_BYTES:
        raise HTTPException(413, "文件过大")
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"path": path, "binary": True, "content": None}
    return {"path": path, "binary": False, "content": text}


@router.post("/{session_id}/upload")
async def upload(session_id: str, file: UploadFile = File(...)):
    root = _session_root(session_id)
    uploads = root / "uploads"
    uploads.mkdir(exist_ok=True)

    raw_name = Path(file.filename or "unnamed").name
    safe_name = SAFE_NAME_RE.sub("_", raw_name) or "unnamed"
    target = (uploads / safe_name).resolve()
    if not str(target).startswith(str(uploads.resolve())):
        raise HTTPException(400, "文件名非法")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "文件超过 10MB")
    target.write_bytes(content)
    return {
        "path": f"uploads/{safe_name}",
        "filename": safe_name,
        "size": len(content),
    }
