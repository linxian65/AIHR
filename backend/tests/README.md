# Backend tests

每个脚本一句话用途 + 运行前置条件。

## 运行方式

```bash
cd backend
python tests/test_xxx.py
```

每个脚本顶部自带 `sys.path.insert` 样板，无需 pytest。

## 脚本清单

| 脚本 | 用途 | 依赖 |
|---|---|---|
| `test_m3.py` | MiniMax 端点连通性 ping | 离线（直连 SDK） |
| `test_agent.py` | ClaudeSDKClient 最小冒烟 | 离线 |
| `test_mcp_e2e.py` | resume_server MCP 工具端到端（旧版） | 离线 |
| `test_approval.py` | stdin 交互审批（旧版） | 离线 |
| `test_approval_unit.py` | approval hook 单测 | 离线 |
| `test_approval_v2.py` | 审批 v2（EventBus） | 离线 |
| `test_pii.py` | PII 脱敏 + 审计日志端到端 | 离线 |
| `test_resume_parse.py` | pdf/docx/txt 解析器直测 | 离线（自造 fixture） |
| `test_http.py` | FastAPI 端到端（直连 8000） | uvicorn :8000 |
| `test_http_via_vite.py` | FastAPI 经 vite 代理端到端 | uvicorn :8000 + vite :5173 |
| `test_files_e2e.py` | files API 端到端（tree/content/traversal） | uvicorn :8000 + vite :5173 |
| `test_approval_e2e.py` | 审批三路径端到端（同意/拒绝/连续） | uvicorn :8000 + vite :5173 |

## 注意事项

- `test_resume_parse.py` 默认造 `workspace/parse_test/uploads/sample.{txt,pdf,docx}` 文件做 fixture；删除该目录即清空 fixture。
- 所有跑 HTTP 的脚本都需要先 `uvicorn app.main:app --port 8000` 和 `cd frontend && npm run dev`。
- `tests/` 不依赖 pytest，加 conftest.py 是为了将来跑 pytest 时自动生效。
