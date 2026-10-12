"""Backend-driven batch resume screening (spec 19A).

Iterates over a list of uploaded resume paths, extracts text, asks the
agent to score each one against a JD, writes per-resume Markdown reports
under `workspace/{sid}/evaluations/`, and emits progress events.

Architecture choice: each evaluation is its own agent run on the shared
ClaudeSDKClient, but driven from the backend loop (not the agent's
internal tool loop). This keeps per-resume failure isolated and lets us
emit coarse-grained progress.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from app.agent_turn import _translate_and_publish
from app.config import WORKSPACE_DIR
from app.mcp_servers.resume_server import extract_resume_text

EmitFn = Callable[[str, dict], Awaitable[None]]

EVAL_PROMPT_TEMPLATE = """请评估以下候选人简历。这是一个独立的评估任务，不需要其他上下文。
岗位要求（JD）：
{jd_text}
简历原文（来自文件：{file_name}）：
---
{resume_text}
---
请输出结构化的评估报告，Markdown 格式，包含以下章节：
- ## 综合评分：X/100
- ## 维度评分（表格：技能匹配 / 经验匹配 / 项目相关性 / 稳定性，0-100）
- ## 优势（3-5 条，每条引用简历原文）
- ## 风险（2-3 条，注明依据）
- ## 建议追问（2-3 个具体问题）
约束：
- 评分中使用 0-100 整数
- 每个结论引用简历具体证据
- 信息不足时明确标注"信息不足"，不要臆测
- 禁止出现年龄、性别、婚育状况等受保护特征
"""


async def _evaluate_one(
    client,
    jd_text: str,
    resume_full_path: Path,
    session_id: str,
    emit: EmitFn,
) -> dict:
    """Run one evaluation against the live client. Returns a result dict."""
    file_name = resume_full_path.name
    text, err = extract_resume_text(resume_full_path)
    if err:
        await emit("batch_error", {"file": file_name, "message": err})
        return {"file": file_name, "ok": False, "error": err}

    prompt = EVAL_PROMPT_TEMPLATE.format(
        jd_text=jd_text, file_name=file_name, resume_text=text,
    )
    output_parts: list[str] = []

    try:
        await client.query(prompt)
        async for msg in client.receive_response():
            async def _collect(event: str, data: dict) -> None:
                if event == "message_delta":
                    output_parts.append(data.get("text", ""))
                # We deliberately don't publish inner per-token deltas as
                # batch events — only the coarse progress signal matters.
            await _translate_and_publish(session_id, msg, _collect)
    except Exception as e:
        msg = f"评估失败: {type(e).__name__}: {e}"
        await emit("batch_error", {"file": file_name, "message": msg})
        return {"file": file_name, "ok": False, "error": msg}

    return {
        "file": file_name,
        "ok": True,
        "evaluation": "".join(output_parts),
    }


async def run_batch_screen(
    session_id: str,
    jd_text: str,
    resume_paths: list[str],
    session_manager,
    event_bus,
    on_event: EmitFn | None = None,
) -> list[dict]:
    """Drive the batch and emit progress. `on_event` (if given) is
    called for every emitted event so the caller can persist them.
    """
    workspace_root = (Path(WORKSPACE_DIR) / session_id).resolve()
    evaluations_dir = workspace_root / "evaluations"
    evaluations_dir.mkdir(parents=True, exist_ok=True)
    total = len(resume_paths)

    async def emit(event: str, data: dict) -> None:
        await event_bus.publish(session_id, {"event": event, "data": data})
        if on_event is not None:
            await on_event(event, data)

    results: list[dict] = []

    try:
        client = await session_manager.get_or_create(session_id)

        for idx, rel_path in enumerate(resume_paths, 1):
            # Path-traversal guard
            try:
                full = (workspace_root / rel_path).resolve()
                if not str(full).startswith(str(workspace_root)):
                    msg = "路径越界"
                    await emit("batch_error", {"file": rel_path, "message": msg})
                    results.append({"file": rel_path, "ok": False, "error": msg})
                    continue
            except Exception as e:
                msg = f"路径解析失败: {e}"
                await emit("batch_error", {"file": rel_path, "message": msg})
                results.append({"file": rel_path, "ok": False, "error": msg})
                continue

            await emit("batch_progress", {
                "completed": idx - 1,
                "total": total,
                "current": full.name,
            })

            r = await _evaluate_one(client, jd_text, full, session_id, emit)
            results.append(r)

            if r["ok"]:
                stem = Path(rel_path).stem
                out = evaluations_dir / f"{stem}.md"
                out.write_text(r["evaluation"], encoding="utf-8")

        # Summary report
        ok_n = sum(1 for r in results if r["ok"])
        fail_n = total - ok_n
        lines = [
            "# 批量评估汇总",
            "",
            f"- 会话：{session_id}",
            f"- 时间：{datetime.now(timezone.utc).isoformat()}",
            f"- 总简历数：{total}",
            f"- 成功：{ok_n}",
            f"- 失败：{fail_n}",
            "",
            "## 各候选人报告",
        ]
        for r in results:
            if r["ok"]:
                lines.append(f"- ✅ {r['file']} → `evaluations/{Path(r['file']).stem}.md`")
            else:
                lines.append(f"- ❌ {r['file']}：{r['error']}")
        summary_path = evaluations_dir / "_summary.md"
        summary_path.write_text("\n".join(lines), encoding="utf-8")

        await emit("batch_complete", {
            "total": total,
            "ok": ok_n,
            "failed": fail_n,
            "summary_path": "evaluations/_summary.md",
        })
    finally:
        await session_manager.end_turn(session_id)

    return results