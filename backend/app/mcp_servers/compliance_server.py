"""MCP server exposing the JD compliance rule library as a tool (spec 20B).

Single tool: check_jd_compliance(jd_text: str) -> JSON { risk_level, issues, summary }

The tool description is the load-bearing instruction that tells the agent
to call this rather than improvise a compliance judgment.
"""
from __future__ import annotations

import json
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from app.compliance_rules import check_compliance


def _err(msg: str) -> dict:
    return {"content": [{"type": "text", "text": json.dumps({"error": msg}, ensure_ascii=False)}]}


def make_compliance_server():
    @tool(
        "check_jd_compliance",
        "检查 JD 是否存在就业歧视性语言或合规风险。当用户要求生成 JD、修改 JD、"
        "或要求检查合规性时，必须调用此工具。不要在未调用工具的情况下自行判断。",
        {"jd_text": str},
    )
    async def check_jd_compliance_tool(args: dict[str, Any]) -> dict:
        jd = str(args.get("jd_text", "")).strip()
        print(f"[compliance_server] check_jd_compliance called, jd_len={len(jd)}")
        if not jd:
            return _err("jd_text 不能为空")
        if len(jd) > 20000:
            return _err("JD 过长（>20000 字符），请截断后重试")
        result = check_compliance(jd)
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result, ensure_ascii=False),
            }]
        }

    return create_sdk_mcp_server(
        name="compliance_server",
        version="0.1.0",
        tools=[check_jd_compliance_tool],
    )


if __name__ == "__main__":
    import asyncio
    from pathlib import Path

    async def _test() -> None:
        server = make_compliance_server()
        print("server:", server)

    asyncio.run(_test())
