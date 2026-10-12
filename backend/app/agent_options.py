"""Build ClaudeAgentOptions wired to MiniMax + per-session resume MCP server."""
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions

from app.config import MINIMAX_BASE_URL, MINIMAX_API_KEY, MINIMAX_MODEL, WORKSPACE_DIR
from app.event_bus import EventBus
from app.hooks.approval import make_can_use_tool
from app.mcp_servers.compliance_server import make_compliance_server
from app.mcp_servers.resume_server import make_resume_server
from app.scenarios import DEFAULT_SCENARIO, get_prompt as get_scenario_prompt

HR_SYSTEM_PROMPT = """
你是 HR 招聘 Agent，通过 MCP 工具与系统交互。
可用工具和使用场景：
1. parse_resume — 当用户要求解析简历、上传简历、或提供简历路径时，必须调用此工具。
   不要直接回答，不要编造简历内容。
2. Read / Glob — 用于读取和写入工作区文件。
工作流：
需求澄清 → JD 生成 → 简历解析 → 候选人评估

当用户要求评估候选人时：
1. 如果简历还没解析，先调用 parse_resume 获取原文
2. 阅读原文，提取关键信息（姓名、技能、经历、教育）
3. 基于岗位要求进行多维度评分，评分输出格式：
   - 综合评分：X/100
   - 技能匹配：X/100
   - 经验匹配：X/100
   - 优势：[3-5 条，每条引用简历原文]
   - 风险：[2-3 条，注明依据]
   - 建议追问：[2-3 个具体问题]
4. 如果用户没有提供 JD，基于常见岗位标准给出初步评估，
   并在报告末尾标注"建议提供原始 JD 以获得更精准的评分"
5. 评分中严禁出现年龄、性别、婚育状况等受保护特征

关于文件路径：
- 用户上传的简历位于 uploads/ 目录下
- 所有相对路径都相对于当前会话的工作区根目录
- 调用 parse_resume 时传相对路径，比如 "uploads/zhangsan.pdf"

输出规范：
- 评分使用 0-100 整数
- 每个结论引用具体证据
- 不确定时标注"信息不足，建议追问"
"""


def build_options(
    session_id: str = "default",
    event_bus: EventBus | None = None,
    prompt_override: str | None = None,
    scenario: str = DEFAULT_SCENARIO,
) -> ClaudeAgentOptions:
    if prompt_override is not None:
        system_prompt = prompt_override
    else:
        scenario_prompt = get_scenario_prompt(scenario)
        if scenario_prompt:
            system_prompt = HR_SYSTEM_PROMPT + "\n\n" + scenario_prompt
        else:
            system_prompt = HR_SYSTEM_PROMPT
    bus = event_bus or EventBus()
    session_root = Path(WORKSPACE_DIR)
    session_dir = session_root / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    resume_server = make_resume_server(session_id, session_root)
    compliance_server = make_compliance_server()
    return ClaudeAgentOptions(
        env={
            "ANTHROPIC_BASE_URL": MINIMAX_BASE_URL,
            "ANTHROPIC_API_KEY": MINIMAX_API_KEY,
            "ANTHROPIC_MODEL": MINIMAX_MODEL,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": MINIMAX_MODEL,
        },
        system_prompt=system_prompt,
        allowed_tools=[
            "mcp__resume_server__parse_resume",
            "mcp__compliance_server__check_jd_compliance",
            "Read",
            "Glob",
        ],
        disallowed_tools=[
            "Bash",
            "BashOutput",
            "KillBash",
            "AskUserQuestion",
        ],
        permission_mode="default",
        mcp_servers={
            "resume_server": resume_server,
            "compliance_server": compliance_server,
        },
        include_partial_messages=True,
        cwd=str(session_dir),
        max_turns=10,
        can_use_tool=make_can_use_tool(session_id, bus),
    )
