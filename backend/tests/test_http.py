"""End-to-end HTTP test: subscribe to SSE, POST a message, collect events.

Expects uvicorn already running on localhost:8000:
    cd backend && uvicorn app.main:app --port 8000

In another terminal:
    python scripts/test_http.py
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = "http://localhost:8000"
SESSION_ID = "http_s1"
TIMEOUT_SEC = 120


def consume_sse(events: list[dict], stop: threading.Event) -> None:
    """Run on a background thread: read SSE stream until server closes or stop fires."""
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
                    events.append({
                        "event": event_name,
                        "data": "\n".join(data_buf),
                    })
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

    # Give the SSE consumer a moment to subscribe before posting.
    time.sleep(0.5)

    print(f"[test_http] POST /api/sessions/{SESSION_ID}/messages")
    resp = httpx.post(
        f"{BASE}/api/sessions/{SESSION_ID}/messages",
        json={"content": "你好，只回复：HTTP OK"},
        timeout=10,
    )
    print(f"[test_http] POST status: {resp.status_code} {resp.text}")

    deadline = time.time() + TIMEOUT_SEC
    while time.time() < deadline:
        if any(e["event"] == "done" for e in events):
            break
        time.sleep(0.2)
    else:
        print("[test_http] TIMEOUT waiting for done event")
        stop.set()
        return 1

    stop.set()
    t.join(timeout=2)

    print(f"\n[test_http] received {len(events)} events:")
    for i, e in enumerate(events):
        try:
            data = json.loads(e["data"])
        except Exception:
            data = e["data"]
        print(f"  [{i:02d}] event={e['event']} data={data}")

    if any(e["event"] == "result" for e in events):
        print("\n[test_http] PASS (got result event)")
        return 0
    print("\n[test_http] FAIL (no result event)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
