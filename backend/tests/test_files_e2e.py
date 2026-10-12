"""Files API e2e test through Vite proxy (port 5173).

Tests:
  A — write file via agent Write tool, then tree + content should reflect it
  B — markdown content rendered (HTTP-level: file content fetch + ext check)
  C — path traversal protection: ../.env, .., encoded ../ → 400
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

VITE = "http://localhost:5173"
TIMEOUT_SEC = 120


def consume_until_done(
    base: str, session_id: str, events_out: list[dict], stop: threading.Event
) -> None:
    with httpx.stream(
        "GET", f"{base}/api/sessions/{session_id}/stream", timeout=None
    ) as resp:
        resp.raise_for_status()
        event_name = "message"
        data_buf: list[str] = []
        for line in resp.iter_lines():
            if stop.is_set():
                break
            if line == "":
                if data_buf:
                    events_out.append({"event": event_name, "data": "\n".join(data_buf)})
                    data_buf = []
                    event_name = "message"
                continue
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_buf.append(line.split(":", 1)[1].strip())


def wait_for(events: list[dict], pred, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred(events):
            return True
        time.sleep(0.1)
    return False


def new_session() -> str:
    return "files_e2e_" + str(int(time.time() * 1000))[-6:]


def trigger_turn(session_id: str, prompt: str) -> list[dict]:
    events: list[dict] = []
    stop = threading.Event()
    t = threading.Thread(
        target=consume_until_done, args=(VITE, session_id, events, stop), daemon=True
    )
    t.start()
    time.sleep(0.4)

    r = httpx.post(
        f"{VITE}/api/sessions/{session_id}/messages",
        json={"content": prompt},
        timeout=10,
    )
    assert r.status_code == 202, f"POST returned {r.status_code}: {r.text}"

    wait_for(events, lambda es: any(e["event"] == "done" for e in es), TIMEOUT_SEC)
    stop.set()
    t.join(timeout=2)
    return events


def test_a_write_file() -> bool:
    sid = new_session()
    print(f"\n========== A write-file  session={sid} ==========")

    events = trigger_turn(
        sid,
        "请用 Write 工具把 'Hello HR Agent' 写入 test.md"
    )
    types = [e["event"] for e in events]
    print(f"[A] event types: {types}")
    if "result" not in types or "done" not in types:
        print("[A] FAIL: missing result/done events")
        return False

    tree_resp = httpx.get(f"{VITE}/api/files/{sid}/tree", timeout=5)
    print(f"[A] tree status: {tree_resp.status_code}")
    tree = tree_resp.json()
    children = tree.get("children", [])
    paths = [c["path"] for c in children]
    print(f"[A] tree paths: {paths}")
    if "test.md" not in paths:
        print("[A] FAIL: test.md not in tree")
        return False

    content_resp = httpx.get(
        f"{VITE}/api/files/{sid}/content",
        params={"path": "test.md"},
        timeout=5,
    )
    print(f"[A] content status: {content_resp.status_code}")
    print(f"[A] content body: {content_resp.text}")
    if content_resp.status_code != 200:
        print("[A] FAIL: content fetch failed")
        return False
    data = content_resp.json()
    if data.get("binary"):
        print("[A] FAIL: file marked binary")
        return False
    if "Hello HR Agent" not in (data.get("content") or ""):
        print(f"[A] FAIL: content does not contain expected text (got {data.get('content')!r})")
        return False

    print("[A] PASS")
    return True


def test_b_markdown() -> bool:
    sid = new_session()
    print(f"\n========== B markdown  session={sid} ==========")

    events = trigger_turn(
        sid,
        "请用 Write 工具把以下内容写入 notes.md："
        "# HR 笔记\n\n- 第一条\n- 第二条\n\n**加粗** 和 *斜体*"
    )
    types = [e["event"] for e in events]
    if "result" not in types or "done" not in types:
        print("[B] FAIL: missing result/done")
        return False

    content_resp = httpx.get(
        f"{VITE}/api/files/{sid}/content",
        params={"path": "notes.md"},
        timeout=5,
    )
    print(f"[B] content status: {content_resp.status_code}")
    if content_resp.status_code != 200:
        print("[B] FAIL: notes.md fetch failed")
        return False
    content = content_resp.json().get("content") or ""
    print(f"[B] notes.md raw:\n{content}")
    for marker in ["# HR 笔记", "- 第一条", "**加粗**", "*斜体*"]:
        if marker not in content:
            print(f"[B] FAIL: markdown source missing {marker!r}")
            return False
    print("[B] PASS (raw source has all markers; markdown rendering is browser-side)")
    return True


def test_c_traversal() -> bool:
    print(f"\n========== C path traversal ==========")
    ok = True

    cases_params = [
        ("../.env", 400),
        ("..", 400),
        ("../other_session/test.md", 400),
    ]
    for path, expected in cases_params:
        r = httpx.get(
            f"{VITE}/api/files/any_session/content",
            params={"path": path},
            timeout=5,
        )
        print(f"[C] params path={path!r} -> HTTP {r.status_code} body={r.text[:100]}")
        if r.status_code != expected:
            print(f"[C] FAIL: expected {expected} got {r.status_code}")
            ok = False

    encoded_url = f"{VITE}/api/files/any_session/content?path=%2e%2e%2f.env"
    r = httpx.get(encoded_url, timeout=5)
    print(f"[C] raw URL %2e%2e%2f.env -> HTTP {r.status_code} body={r.text[:100]}")
    if r.status_code != 400:
        print(f"[C] FAIL: encoded traversal expected 400 got {r.status_code}")
        ok = False

    if ok:
        print("[C] PASS")
    return ok


def main() -> int:
    results = [
        test_a_write_file(),
        test_b_markdown(),
        test_c_traversal(),
    ]
    print("\n========== summary ==========")
    for label, ok in zip(["A write-file", "B markdown", "C traversal"], results):
        print(f"  {label}: {'PASS' if ok else 'FAIL'}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
