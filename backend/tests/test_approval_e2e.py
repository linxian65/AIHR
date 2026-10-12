"""Approval flow end-to-end test through Vite proxy (port 5173).

Three paths:
  A — approve: send_email → approval_required → POST approve=true → tool executes
  B — deny   : send_email → approval_required → POST approve=false → tool blocked, audit decision=deny
  C — two approvals in one turn: prompt asks agent to send 2 emails; expect 2 approval_required events

Validates:
  - SSE streams approval_required events
  - GET /api/sessions/{sid}/approvals returns pending list
  - POST decide response is {ok, approval_id, approved}
  - audit.log.jsonl contains allow/deny with correct decision + reason

Pre-req: uvicorn :8000 + vite :5173 already running.
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
from pathlib import Path
from typing import Iterator

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

VITE = "http://localhost:5173"
TIMEOUT_SEC = 120
AUDIT_PATH = Path(__file__).resolve().parent.parent / "workspace" / "audit.log.jsonl"


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


def wait_for(events: list[dict], predicate, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate(events):
            return True
        time.sleep(0.1)
    return False


def get_approval_id(events: list[dict]) -> str | None:
    for e in events:
        if e["event"] != "approval_required":
            continue
        try:
            return json.loads(e["data"])["approval_id"]
        except Exception:
            continue
    return None


def new_session() -> str:
    return "appr_e2e_" + str(int(time.time() * 1000))[-6:]


def run_path(label: str, prompt: str, decide: bool, reason: str | None) -> bool:
    sid = new_session()
    print(f"\n========== {label}  session={sid} ==========")
    events: list[dict] = []
    stop = threading.Event()
    t = threading.Thread(
        target=consume_until_done, args=(VITE, sid, events, stop), daemon=True
    )
    t.start()
    time.sleep(0.4)

    print(f"[{label}] POST /api/sessions/{sid}/messages")
    r = httpx.post(
        f"{VITE}/api/sessions/{sid}/messages",
        json={"content": prompt},
        timeout=10,
    )
    print(f"[{label}] POST status: {r.status_code} {r.text}")
    if r.status_code != 202:
        stop.set()
        return False

    if not wait_for(events, lambda es: any(e["event"] == "approval_required" for e in es), 30):
        print(f"[{label}] FAIL: no approval_required event")
        stop.set()
        return False

    aid = get_approval_id(events)
    assert aid is not None
    print(f"[{label}] approval_id={aid}")

    list_resp = httpx.get(f"{VITE}/api/sessions/{sid}/approvals", timeout=5)
    print(f"[{label}] GET /approvals -> {list_resp.status_code} {list_resp.text}")
    if list_resp.status_code != 200 or aid not in list_resp.json().get("pending", []):
        print(f"[{label}] FAIL: GET /approvals missing pending")
        stop.set()
        return False

    body = {"approved": decide, "reason": reason}
    dec_resp = httpx.post(
        f"{VITE}/api/sessions/{sid}/approvals/{aid}",
        json=body,
        timeout=5,
    )
    print(f"[{label}] POST /approvals/{{aid}} -> {dec_resp.status_code} {dec_resp.text}")
    dec = dec_resp.json()
    if dec.get("ok") is not True or dec.get("approval_id") != aid or dec.get("approved") != decide:
        print(f"[{label}] FAIL: unexpected decide response: {dec}")
        stop.set()
        return False

    if not wait_for(events, lambda es: any(e["event"] == "done" for e in es), TIMEOUT_SEC):
        print(f"[{label}] FAIL: no done event after decision")
        stop.set()
        return False

    stop.set()
    t.join(timeout=2)

    types = [e["event"] for e in events]
    print(f"[{label}] event types: {types}")

    has_result = "result" in types
    has_done = "done" in types
    has_tool_use_start = "tool_use_start" in types
    has_tool_use_result = "tool_use_result" in types

    if not (has_result and has_done and has_tool_use_start and has_tool_use_result):
        print(f"[{label}] FAIL: missing required events")
        return False

    if decide:
        for e in events:
            if e["event"] == "tool_use_result":
                d = json.loads(e["data"])
                if d.get("success") is True:
                    break
        else:
            print(f"[{label}] FAIL: tool_use_result not success")
            return False
    else:
        for e in events:
            if e["event"] == "tool_use_result":
                d = json.loads(e["data"])
                if d.get("success") is False:
                    break
        else:
            print(f"[{label}] FAIL: tool_use_result not failure")
            return False

    print(f"[{label}] PASS")
    return True


def audit_decision_for(sid: str, tool: str) -> tuple[str, str | None] | None:
    if not AUDIT_PATH.exists():
        return None
    last: tuple[str, str | None] | None = None
    for line in AUDIT_PATH.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("session_id") == sid and rec.get("tool_name") == tool:
            last = (rec.get("decision"), rec.get("reason"))
    return last


def run_path_c() -> bool:
    sid = new_session()
    print(f"\n========== C two-emails  session={sid} ==========")
    events: list[dict] = []
    stop = threading.Event()
    t = threading.Thread(
        target=consume_until_done, args=(VITE, sid, events, stop), daemon=True
    )
    t.start()
    time.sleep(0.4)

    r = httpx.post(
        f"{VITE}/api/sessions/{sid}/messages",
        json={"content": (
            "请调用两次 send_email 工具。"
            "第一次：to=a@x.com, subject='first', body='first body'。"
            "第二次：to=b@y.com, subject='second', body='second body'。"
            "两次都发，不要省略。"
        )},
        timeout=10,
    )
    print(f"[C] POST status: {r.status_code}")
    if r.status_code != 202:
        stop.set()
        return False

    approved_count = 0
    deadline = time.time() + 120
    while time.time() < deadline:
        if any(e["event"] == "done" for e in events):
            break
        pending = httpx.get(
            f"{VITE}/api/sessions/{sid}/approvals", timeout=5
        ).json().get("pending", [])
        for aid in pending:
            httpx.post(
                f"{VITE}/api/sessions/{sid}/approvals/{aid}",
                json={"approved": True},
                timeout=5,
            )
            approved_count += 1
        time.sleep(0.4)

    stop.set()
    t.join(timeout=2)

    approval_count = sum(1 for e in events if e["event"] == "approval_required")
    print(f"[C] approval_required={approval_count}, approved={approved_count}")
    if approval_count < 2 or approved_count < 2:
        print("[C] FAIL: need at least 2 approvals")
        return False
    success_count = sum(
        1 for e in events
        if e["event"] == "tool_use_result"
        and json.loads(e["data"]).get("success") is True
    )
    print(f"[C] tool_use_result success count = {success_count}")
    if success_count < 2:
        print("[C] FAIL: both tool results should be success")
        return False
    if not any(e["event"] == "result" for e in events):
        print("[C] FAIL: no result event")
        return False
    print("[C] PASS")
    return True


def main() -> int:
    results: list[bool] = []

    results.append(run_path(
        "A approve",
        "请调用 send_email 工具，参数：to=zhangsan@example.com, subject='面试邀请', "
        "body='请周五下午2点参加面试'。",
        decide=True,
        reason=None,
    ))

    sid_b: str | None = None
    b_pass = True
    sid = new_session()
    sid_b = sid
    print(f"\n========== B deny  session={sid} ==========")
    events: list[dict] = []
    stop = threading.Event()
    t = threading.Thread(
        target=consume_until_done, args=(VITE, sid, events, stop), daemon=True
    )
    t.start()
    time.sleep(0.4)
    httpx.post(
        f"{VITE}/api/sessions/{sid}/messages",
        json={"content": (
            "请调用 send_email 工具，参数：to=zhangsan@example.com, "
            "subject='面试邀请', body='请周五下午2点参加面试'。"
        )},
        timeout=10,
    )
    if wait_for(events, lambda es: any(e["event"] == "approval_required" for e in es), 30):
        aid = get_approval_id(events)
        assert aid is not None
        httpx.post(
            f"{VITE}/api/sessions/{sid}/approvals/{aid}",
            json={"approved": False, "reason": "测试拒绝"},
            timeout=5,
        )
        wait_for(events, lambda es: any(e["event"] == "done" for e in es), TIMEOUT_SEC)
        stop.set()
        t.join(timeout=2)
        tool_result_failed = False
        for e in events:
            if e["event"] == "tool_use_result":
                d = json.loads(e["data"])
                if d.get("success") is False:
                    tool_result_failed = True
                    break
        if not tool_result_failed:
            print("[B deny] FAIL: tool_use_result did not report success=False")
            b_pass = False
        print(f"[B deny] event types: {[e['event'] for e in events]}")
    else:
        print("[B deny] FAIL: no approval_required")
        b_pass = False
        stop.set()
    results.append(b_pass)

    time.sleep(0.5)
    audit_b = audit_decision_for(sid_b, "mcp__resume_server__send_email") if sid_b else None
    print(f"\n[B deny] audit log entry: {audit_b}")
    if audit_b is None or audit_b[0] != "deny":
        print("[B deny] FAIL: audit log missing or decision != deny")
        results[-1] = False
    if audit_b is not None and audit_b[1] != "测试拒绝":
        print(f"[B deny] FAIL: audit reason != 测试拒绝 (got {audit_b[1]!r})")
        results[-1] = False
    if audit_b is not None and audit_b[0] == "deny":
        print("[B deny] PASS")

    results.append(run_path_c())

    print("\n========== summary ==========")
    labels = ["A approve", "B deny", "C two-emails"]
    for label, ok in zip(labels, results):
        print(f"  {label}: {'PASS' if ok else 'FAIL'}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
