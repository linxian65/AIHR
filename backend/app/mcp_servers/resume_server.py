"""Per-session MCP server for resume parsing + email sending.

The server is constructed per session via make_resume_server(session_id, workspace_root)
so parse_resume can resolve paths against the session's own uploads/ directory.
"""
import json
from pathlib import Path
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

MAX_TEXT_CHARS = 20000


def _err(msg: str) -> dict:
    return {"content": [{"type": "text", "text": json.dumps({"error": msg}, ensure_ascii=False)}]}


def _extract_pdf(path: Path) -> str:
    import pdfplumber
    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            parts.append(t)
    return "\n\n".join(parts).strip()


def _extract_docx(path: Path) -> str:
    from docx import Document
    doc = Document(str(path))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(parts).strip()


def _extract_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip()


EXTRACTORS = {
    ".pdf": _extract_pdf,
    ".docx": _extract_docx,
    ".txt": _extract_txt,
}


def extract_resume_text(full_path: Path) -> tuple[str, str]:
    """Extract text from a resume file.

    Returns (text, error_message). On success error_message is empty.
    """
    if not full_path.exists():
        return "", f"文件不存在: {full_path.name}"
    if not full_path.is_file():
        return "", f"不是文件: {full_path.name}"
    ext = full_path.suffix.lower()
    extractor = EXTRACTORS.get(ext)
    if extractor is None:
        return "", f"不支持的文件类型: {ext}"
    try:
        text = extractor(full_path)
    except Exception as e:
        return "", f"解析失败: {type(e).__name__}: {e}"
    if not text.strip():
        return "", "解析结果为空（可能是扫描版 PDF 或加密文档）"
    return text[:MAX_TEXT_CHARS], ""


def make_resume_server(session_id: str, workspace_root: Path):
    """Build an MCP server bound to session_id's uploads directory."""
    base = (workspace_root / session_id).resolve()

    @tool(
        "parse_resume",
        "解析简历文件，返回简历原文。当用户上传简历或要求解析简历时调用。"
        "file_path 是相对于工作区根目录的路径，比如 uploads/zhangsan.pdf。",
        {"file_path": str},
    )
    async def parse_resume(args: dict[str, Any]) -> dict:
        rel = str(args.get("file_path", "")).strip()
        print(f"[resume_server] parse_resume called: {rel}")
        if not rel:
            return _err("file_path 不能为空")
        try:
            full = (base / rel).resolve()
            base_resolved = base.resolve()
            if not str(full).startswith(str(base_resolved)):
                return _err("路径越界，不允许访问工作区之外的文件")
        except Exception as e:
            return _err(f"路径解析失败: {e}")
        text, err = extract_resume_text(full)
        if err:
            return _err(err)
        truncated = text
        payload = {
            "file_path": rel,
            "file_name": full.name,
            "char_count": len(text),
            "truncated": len(text) > MAX_TEXT_CHARS,
            "raw_text": truncated,
        }
        return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}

    @tool(
        "send_email",
        "向候选人发送邮件。只有当用户明确要求发送邮件时调用。",
        {"to": str, "subject": str, "body": str},
    )
    async def send_email(args: dict[str, Any]) -> dict:
        print(f"[resume_server] send_email called: to={args.get('to')}")
        return {"content": [{"type": "text", "text": f"邮件已发送给 {args.get('to')}"}]}

    return create_sdk_mcp_server(
        name="resume_server",
        version="0.2.0",
        tools=[parse_resume, send_email],
    )


if __name__ == "__main__":
    import asyncio

    async def _test() -> None:
        server = make_resume_server("smoke", Path("workspace"))
        print("server:", server)

    asyncio.run(_test())