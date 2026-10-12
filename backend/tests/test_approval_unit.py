"""Direct unit test of can_use_tool factory (v2 EventBus flow)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claude_agent_sdk import (
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

from app.event_bus import EventBus
from app.hooks.approval import (
    is_dangerous,
    make_can_use_tool,
    resolve_approval,
)


async def resolver_loop(q: asyncio.Queue, session: str, approved: bool) -> None:
    while True:
        ev = await q.get()
        if ev.get("event") == "approval_required":
            resolve_approval(session, ev["data"]["approval_id"], approved=approved)


async def main() -> None:
    print("is_dangerous regex sanity:")
    for name in [
        "mcp__resume_server__send_email",
        "mcp__ats_server__update_status",
        "mcp__foo__notify_admin",
        "mcp__mail__email_user",
        "mcp__resume_server__parse_resume",
        "Read",
    ]:
        print(f"  {name:45s} -> {is_dangerous(name)}")

    session = "unit_test"
    bus = EventBus()
    can_use_tool = make_can_use_tool(session, bus)
    ctx = ToolPermissionContext(suggestions=[], tool_use_id="t1")

    # Case 1: safe tool -> allow (no resolver needed)
    r = await can_use_tool(
        "mcp__resume_server__parse_resume",
        {"file_path": "/tmp/x.pdf"},
        ctx,
    )
    assert isinstance(r, PermissionResultAllow), f"expected allow, got {type(r)}"
    print("[case 1] safe tool -> allow  OK")

    # Case 2: dangerous + y -> allow
    q = bus.subscribe(session)
    sub = asyncio.create_task(resolver_loop(q, session, approved=True))
    try:
        r = await can_use_tool(
            "mcp__resume_server__send_email",
            {"to": "x@y.com", "subject": "hi", "body": "..."},
            ctx,
        )
        assert isinstance(r, PermissionResultAllow), f"expected allow, got {type(r)}"
        print("[case 2] dangerous + y -> allow  OK")
    finally:
        sub.cancel()
        bus.unsubscribe(session, q)

    # Case 3: dangerous + n -> deny
    q = bus.subscribe(session)
    sub2 = asyncio.create_task(resolver_loop(q, session, approved=False))
    try:
        r = await can_use_tool(
            "mcp__resume_server__send_email",
            {"to": "x@y.com", "subject": "hi", "body": "..."},
            ctx,
        )
        assert isinstance(r, PermissionResultDeny), f"expected deny, got {type(r)}"
        print(f"[case 3] dangerous + n -> deny  OK  (message: {r.message!r})")
    finally:
        sub2.cancel()
        bus.unsubscribe(session, q)

    print("\n=== APPROVAL UNIT TEST DONE ===")


if __name__ == "__main__":
    asyncio.run(main())
