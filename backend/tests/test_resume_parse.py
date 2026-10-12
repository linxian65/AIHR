"""Direct test of resume parsers (txt / pdf / docx).

Usage:
    cd backend && python scripts/test_resume_parse.py

For pdf/docx testing, drop a real file into:
    backend/workspace/parse_test/uploads/sample.pdf  (or .docx)
If no file present, the corresponding branch is skipped (no error).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import WORKSPACE_DIR
from app.mcp_servers.resume_server import (
    _extract_docx,
    _extract_pdf,
    _extract_txt,
    make_resume_server,
)


SESSION_ID = "parse_test"


def setup_test_files(base: Path) -> Path:
    uploads = base / SESSION_ID / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    txt = uploads / "sample.txt"
    if not txt.exists():
        txt.write_text(
            "姓名：李四\n技能：Python, Go, K8s\n经验：5 年\n公司：某大厂\n",
            encoding="utf-8",
        )
    return uploads


def test_txt(uploads: Path) -> None:
    print("\n========== test txt ==========")
    p = uploads / "sample.txt"
    text = _extract_txt(p)
    print(f"path: {p}")
    print(f"chars: {len(text)}")
    print(f"content:\n{text}")
    assert "李四" in text and "Python" in text


def test_pdf_if_present(uploads: Path) -> None:
    print("\n========== test pdf (if present) ==========")
    p = uploads / "sample.pdf"
    if not p.exists():
        print(f"[skip] no PDF at {p} — drop a real .pdf here to test pdfplumber")
        return
    text = _extract_pdf(p)
    print(f"path: {p}")
    print(f"chars: {len(text)}")
    print(f"first 500 chars:\n{text[:500]}")


def test_docx_if_present(uploads: Path) -> None:
    print("\n========== test docx (if present) ==========")
    p = uploads / "sample.docx"
    if not p.exists():
        print(f"[skip] no DOCX at {p} — drop a real .docx here to test python-docx")
        return
    text = _extract_docx(p)
    print(f"path: {p}")
    print(f"chars: {len(text)}")
    print(f"first 500 chars:\n{text[:500]}")


def test_make_resume_server() -> None:
    print("\n========== test make_resume_server ==========")
    server = make_resume_server(SESSION_ID, Path(WORKSPACE_DIR))
    print(f"server: {server}")
    assert server is not None


def main() -> int:
    base = Path(WORKSPACE_DIR)
    uploads = setup_test_files(base)
    print(f"workspace base: {base}")
    print(f"uploads dir: {uploads}")
    try:
        test_txt(uploads)
        test_pdf_if_present(uploads)
        test_docx_if_present(uploads)
        test_make_resume_server()
    except Exception as e:
        print(f"\nFAIL: {type(e).__name__}: {e}")
        return 1
    print("\n=== resume parse smoke PASS ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
