# HR Recruit Agent

一个基于 Claude Agent SDK + MiniMax M3 的招聘 Agent 工作台。覆盖需求澄清、JD 生成、简历解析、候选人评估、面试指南、HR 政策问答六大场景。

## 功能

- 岗位需求澄清 + JD 生成（多轮反问，不一次问 5 个）
- 简历批量解析与评分（PDF / DOCX / TXT）
- 面试指南生成（基于简历内容定制追问）
- HR 政策问答（劳动法 / 社保 / 合同 / 合规）
- 人工审批（human-in-the-loop）— 所有外发操作（邮件 / ATS）必须人工点头
- PII 自动脱敏（手机 / 身份证 / 邮箱）
- 路径穿越防护（按会话隔离的 workspace + 双重 resolve 检查）
- 审计日志（JSONL，按工具 + 决策 + PII 命中数）

## 架构

- **Agent 外壳**：[Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) (Python)
- **底层模型**：MiniMax M3（Anthropic 兼容 API）
- **MCP 工具**：进程内运行（`mcp_servers/resume_server.py`），按 session_id 闭包构建
- **后端**：FastAPI + SSE（`sse-starlette`）
- **前端**：Vite + React + antd + Zustand
- **会话元数据**：JSON 文件（`backend/data/sessions.json`）+ asyncio.Lock，刷新页面后仍可恢复会话列表
- **工作区隔离**：每个 session 独立 `workspace/<sid>/`，路径穿越防护

## 快速开始

### 依赖

- Python 3.11+
- Node.js 18+
- 一个 MiniMax 订阅 Key（写到 `backend/.env`）

### 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env
# 编辑 .env 填入 MINIMAX_API_KEY
./start.sh                           # Windows: .\start.ps1
```

后端监听 http://127.0.0.1:8000

### 前端

```bash
cd frontend
./start.sh                           # Windows: .\start.ps1
```

打开 http://localhost:5174

## 目录结构

```
hr-recruit-agent/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── config.py               # .env 加载
│   │   ├── scenarios.py            # 5 个场景的 prompt 片段
│   │   ├── session_store.py        # JSON 会话元数据
│   │   ├── session_manager.py      # per-session ClaudeSDKClient
│   │   ├── agent_turn.py           # 单 turn 翻译 SDK → EventBus
│   │   ├── event_bus.py            # asyncio queue per session
│   │   ├── agent_options.py        # ClaudeAgentOptions 工厂
│   │   ├── mcp_servers/
│   │   │   └── resume_server.py    # parse_resume 工具
│   │   ├── hooks/
│   │   │   ├── approval.py         # 人工审批 can_use_tool
│   │   │   └── pii.py              # PII 脱敏 + 审计
│   │   └── api/
│   │       ├── sessions.py         # POST /sessions/{sid}/messages
│   │       ├── sessions_meta.py    # GET/POST/PATCH/DELETE + /scenarios
│   │       ├── stream.py           # SSE 端点
│   │       ├── approvals.py        # 审批端点
│   │       └── files.py            # tree / content / upload
│   ├── tests/                      # 直跑 + pytest 兼容
│   │   ├── test_m3.py              # MiniMax 端点连通
│   │   ├── test_agent.py           # ClaudeSDKClient 冒烟
│   │   ├── test_pii.py             # PII 脱敏 + 审计
│   │   ├── test_resume_parse.py    # 解析器直测
│   │   ├── test_http.py            # FastAPI 端到端
│   │   ├── test_files_e2e.py       # 文件 API
│   │   ├── test_approval_e2e.py     # 审批三路径
│   │   └── demo_end_to_end.py      # 完整演示
│   ├── workspace/                  # 每个 session 一个子目录（不入库）
│   ├── data/                       # sessions.json（不入库）
│   ├── start.sh / start.ps1
│   └── pyproject.toml
└── frontend/
    ├── src/
    │   ├── App.tsx                 # 顶栏 + Tabs + 三栏布局
    │   ├── stores/sessionStore.ts  # zustand（多会话 + 消息隔离）
    │   ├── api/                    # fetch 包装
    │   ├── hooks/useSSE.ts         # EventSource 消费者
    │   └── components/             # SessionList / MessageStream / ChatInput / UploadZone / FileTree / FilePreview / ApprovalPanel
    └── start.sh / start.ps1
```

## 场景命令

在前端对话输入框直接敲斜杠命令，会切换当前会话的场景：

| 命令 | 场景 | 用途 |
|---|---|---|
| `/jd` | 岗位澄清 + JD 生成 | 多轮反问 → 画像卡 → JD |
| `/screen` | 简历批量评估 | parse + 多维评分 + 横向对比 |
| `/interview` | 面试指南生成 | 基于简历的个性化追问 |
| `/policy` | HR 政策问答 | 劳动法 / 社保 / 合同 |

也可在新建会话时选场景，或顶栏 Select 切换。

## 安全边界

- **人工审批**：所有外发操作（`send_email`、`notify_*`、`ats_*`）必须经 `can_use_tool` 钩子，前端 ApprovalPanel 点头
- **PII 脱敏**：`Write/Edit` 入参走正则识别手机/身份证/邮箱，写入前替换为 `[手机号已脱敏]` 等
- **路径防护**：所有路径解析走 `(base/rel).resolve() + startswith(base_resolved)` 双重检查
- **Bash 禁用**：`disallowed_tools` 显式列出 `Bash/BashOutput/KillBash/AskUserQuestion`
- **API key**：`.env` 入 `.gitignore`，仓库只留 `.env.example`
- **本地数据不入库**：`workspace/` 和 `data/` 都在 `.gitignore` 里

## 测试

```bash
cd backend

# 直跑（不依赖 pytest）
python tests/test_m3.py
python tests/test_agent.py
python tests/test_pii.py
python tests/test_approval_e2e.py     # 需 uvicorn :8000 + vite :5174
python tests/test_files_e2e.py        # 需 uvicorn :8000 + vite :5174
python tests/demo_end_to_end.py       # 需 uvicorn :8000，单一演示脚本
```

## 已知限制

- M3 在 Anthropic 兼容协议下的工具路由准确率约 60–80%（[结果诊断与回归案例]）
- 单会话消息历史未持久化到磁盘（前端内存保留，刷新丢失；后端不存消息体）
- 审批队列未做跨标签页同步
- 中文文件名在 Windows mingw bash + curl 下会出现 mojibake（服务端正确，前端 fetch 正常）
