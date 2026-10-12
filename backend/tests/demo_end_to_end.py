"""End-to-end demo: full HR Recruit Agent flow via pure HTTP.

Walks the entire "招后端工程师" lifecycle:
  0. create session (scenario=jd)
  1. describe role -> agent batches clarifying questions
  2. answer clarifying questions -> agent outputs role profile / JD
  3. upload resume (TXT)
  4. trigger resume parse + scoring
  5. summarize tool calls
  6. fetch workspace file tree
  7. tail audit log

Pre-req: uvicorn app.main:app --port 8000 already running.
No frontend needed; safe for CI.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = "http://127.0.0.1:8000"
SESSION_ID = "demo_e2e_001"


async def collect_sse(client: httpx.AsyncClient, session_id: str, stop_on_done: bool = True) -> list[dict]:
    """Subscribe to SSE; return all events as [{event, data}]."""
    events: list[dict] = []
    current_event: str | None = None
    async with client.stream("GET", f"{BASE}/api/sessions/{session_id}/stream", timeout=None) as resp:
        async for line in resp.aiter_lines():
            if not line:
                continue
            if line.startswith("event: "):
                current_event = line[7:].strip()
            elif line.startswith("data: ") and current_event:
                data = json.loads(line[6:])
                events.append({"event": current_event, "data": data})
                if stop_on_done and current_event == "done":
                    return events
                current_event = None
    return events


async def send_and_wait(client: httpx.AsyncClient, session_id: str, content: str) -> list[dict]:
    """POST a message and wait for SSE done event."""
    async def _send() -> None:
        await asyncio.sleep(0.1)
        await client.post(
            f"{BASE}/api/sessions/{session_id}/messages",
            json={"content": content},
        )

    send_task = asyncio.create_task(_send())
    events = await collect_sse(client, session_id)
    await send_task
    return events


def _text(events: list[dict]) -> str:
    return "".join(e["data"].get("text", "") for e in events if e["event"] == "message_delta")


async def main() -> None:
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 0. 建会话
        print("\n=== 0. 新建会话（场景：jd）===")
        r = await client.post(f"{BASE}/api/sessions", json={
            "session_id": SESSION_ID,
            "title": "招后端工程师",
            "scenario": "jd",
        })
        print(r.json())

        # 1. 需求澄清
        print("\n=== 1. 描述岗位需求，观察 agent 分批反问 ===")
        events = await send_and_wait(client, SESSION_ID, "我想招一个高级后端工程师，AI Infra 方向")
        text = _text(events)
        print(text[:500])

        # 2. 回答澄清问题
        print("\n=== 2. 回答澄清问题 ===")
        events = await send_and_wait(
            client, SESSION_ID,
            "核心产出是训练平台的调度系统；是新增岗位；必须熟悉 Kubernetes 和 Ray；不带团队；预算 50-70 万"
        )
        text = _text(events)
        print(text[:800])

        # 3. 上传简历
        print("\n=== 3. 上传简历 ===")
        resume_path = Path("/tmp/demo_resume.txt")
        resume_path.write_text(
            "姓名：张三\n"
            "技能：Python, Kubernetes, Ray, NCCL\n"
            "经验：5 年\n"
            "公司：某大厂\n"
            "项目：主导 1000+ GPU 集群调度系统\n",
            encoding="utf-8",
        )
        with open(resume_path, "rb") as f:
            r = await client.post(
                f"{BASE}/api/files/{SESSION_ID}/upload",
                files={"file": ("demo_resume.txt", f, "text/plain")},
            )
        print(r.json())

        # 4. 触发解析 + 评分
        print("\n=== 4. 触发简历解析 + 评分 ===")
        events = await send_and_wait(client, SESSION_ID, "请评估刚上传的简历：uploads/demo_resume.txt")
        text = _text(events)
        print(text[:1500])

        # 5. 工具调用汇总
        print("\n=== 5. 工具调用汇总 ===")
        for e in events:
            if e["event"] == "tool_use_start":
                print(f"  [TOOL] {e['data']['name']}: {json.dumps(e['data']['input'], ensure_ascii=False)[:120]}")

        # 6. 文件树
        print("\n=== 6. 文件树 ===")
        r = await client.get(f"{BASE}/api/files/{SESSION_ID}/tree")
        print(json.dumps(r.json(), ensure_ascii=False, indent=2)[:800])

        # 7. 审计日志尾部
        print("\n=== 7. 审计日志尾部 ===")
        audit = Path(__file__).resolve().parent.parent / "workspace" / "audit.log.jsonl"
        if audit.exists():
            lines = audit.read_text(encoding="utf-8").strip().split("\n")
            for line in lines[-5:]:
                print(" ", line[:200])

        print("\n=== DEMO COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
