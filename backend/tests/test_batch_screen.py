"""End-to-end smoke test for the batch screening endpoint (spec 19A).

Three minimal resumes get uploaded, the batch endpoint fires, SSE is
subscribed in a side task, then we verify the file tree and event flow.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
SID = "batch_test_001"


async def main() -> int:
    async with httpx.AsyncClient(timeout=300) as client:
        # 1. Create session (idempotent — re-running won't error)
        r = await client.post(
            f"{BASE}/api/sessions",
            json={"session_id": SID, "title": "批量测试"},
        )
        print(f"[create] {r.status_code} {r.text[:120]}")

        # 2. Upload 3 fake resumes
        paths: list[str] = []
        for i in range(1, 4):
            content = (
                f"姓名：候选人{i}\n"
                f"技能：Python, K8s\n"
                f"经验：{i + 3} 年\n"
                f"项目：项目{i}\n"
            )
            r = await client.post(
                f"{BASE}/api/files/{SID}/upload",
                files={"file": (f"resume_{i}.txt", content.encode("utf-8"), "text/plain")},
            )
            data = r.json()
            paths.append(data["path"])
        print(f"[upload] paths={paths}")

        # 3. Fire batch screen
        r = await client.post(
            f"{BASE}/api/sessions/{SID}/batch-screen",
            json={
                "jd_text": "高级后端，要求 Python + K8s，3 年以上经验",
                "resume_paths": paths,
            },
        )
        print(f"[batch] {r.status_code} {r.text[:160]}")
        if r.status_code != 202:
            return 1

        # 4. Subscribe to SSE in parallel, log only the batch events we care about
        async def watch() -> None:
            async with client.stream(
                "GET", f"{BASE}/api/sessions/{SID}/stream"
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("event:"):
                        ev = line.split(":", 1)[1].strip()
                        if ev in (
                            "batch_progress", "batch_error",
                            "batch_complete", "done",
                        ):
                            print(f"  SSE [{ev}]")

        watcher = asyncio.create_task(watch())
        try:
            await asyncio.wait_for(watcher, timeout=180)
        except asyncio.TimeoutError:
            print("[watch] SSE timeout (180s) — continuing")

        # 5. Inspect the resulting evaluations tree
        r = await client.get(f"{BASE}/api/files/{SID}/tree")
        tree = r.json()
        print("[tree]")
        for child in tree.get("children", []):
            if child["name"] == "evaluations":
                for f in child.get("children", []):
                    print(f"  evaluations/{f['name']}")
            else:
                print(f"  {child['name']}/")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))