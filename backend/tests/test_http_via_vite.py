"""End-to-end HTTP test through Vite proxy (port 5173) — what the browser does."""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = "http://localhost:5173"
SESSION_ID = "fe_s1"
TIMEOUT_SEC = 120


def consume_sse(events: list[dict], stop: threading.Event) -> None:
    with httpx.stream(
        "GET", f"{BASE}/api/sessions/{SESSION_ID}/stream", timeout=None
    ) as resp:
        resp.raise_for_status()
        event_name = "message"
        data_buf: list[str] = []
        for line in resp.iter_lines():
            if stop.is_set():
                break
            if line == "":
                if data_buf:
                    events.append({"event": event_name, "data": "\n".join(data_buf)})
                    data_buf = []
                    event_name = "message"
                continue
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_buf.append(line.split(":", 1)[1].strip())


def main() -> int:
    events: list[dict] = []
    stop = threading.Event()
    t = threading.Thread(target=consume_sse, args=(events, stop), daemon=True)
    t.start()

    time.sleep(0.5)

    print(f"[via-vite] POST {BASE}/api/sessions/{SESSION_ID}/messages")
    resp = httpx.post(
        f"{BASE}/api/sessions/{SESSION_ID}/messages",
        json={"content": "你好，只回复：前端 OK"},
        timeout=10,
    )
    print(f"[via-vite] POST status: {resp.status_code} {resp.text}")

    deadline = time.time() + TIMEOUT_SEC
    while time.time() < deadline:
        if any(e["event"] == "done" for e in events):
            break
        time.sleep(0.2)
    else:
        print("[via-vite] TIMEOUT waiting for done event")
        stop.set()
        return 1

    stop.set()
    t.join(timeout=2)

    print(f"\n[via-vite] received {len(events)} events:")
    for i, e in enumerate(events):
        try:
            data = json.loads(e["data"])
        except Exception:
            data = e["data"]
        print(f"  [{i:02d}] event={e['event']} data={data}")

    has_result = any(e["event"] == "result" for e in events)
    has_message_delta = any(e["event"] == "message_delta" for e in events)
    has_thinking_delta = any(e["event"] == "thinking_delta" for e in events)

    if has_result and has_message_delta and has_thinking_delta:
        print("\n[via-vite] PASS (got result + message_delta + thinking_delta)")
        return 0
    print("\n[via-vite] FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
