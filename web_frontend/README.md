# MassAgent 网页前端

本目录包含 MassAgent 的 Web UI 与 FastAPI 后端，与 `src/` 中的 MCP 质谱分析工具通过 Agent 流水线对接。

## 目录结构

```
web_frontend/
├── index.html              # 单页应用入口（会话侧栏 + 聊天 + 文件面板）
├── static/
│   ├── app.js              # 前端逻辑：会话、消息、SSE、附件、文件列表
│   └── styles.css          # 页面样式与三栏布局
├── backend/
│   ├── webapp.py           # FastAPI 应用、REST/SSE API、静态资源挂载
│   ├── agent_runner.py     # Web Agent 执行（调用 MCP 工具链，与 run_agent 类似）
│   ├── session_storage.py  # SQLite 会话/消息持久化
│   ├── agent_jobs.py       # 后台任务与取消（终止生成）
│   └── json_parse.py       # Agent 输出中的 JSON / tool_call 解析
├── data/
│   └── sessions.sqlite3    # 会话数据库（运行时自动创建）
└── README.md               # 本说明
```

`src/webapp.py`、`src/web_agent_runner.py` 等保留为**兼容 shim**，仅 re-export `web_frontend.backend` 中的实现，便于旧命令继续可用。

## 启动方式

在项目根目录、已激活 `MOA` 环境后：

```powershell
cd E:\bin\shixi\MassAgent
python -m uvicorn web_frontend.backend.webapp:app --host 0.0.0.0 --port 8010
```

浏览器访问：`http://127.0.0.1:8010`

## 各文件用途

### 前端

| 文件 | 用途 |
|------|------|
| `index.html` | 页面骨架：左侧会话列表与工具说明，中间聊天区，右侧「会话文件」面板（输入 inputspace / 输出 outputspace） |
| `static/app.js` | 会话 CRUD、模型选择、工具列表展示、附件上传、SSE 流式对话、Agent 模式、分享链接、终止生成、工作区文件树加载 |
| `static/styles.css` | 深色侧栏、聊天区、Composer、消息气泡、文件面板与响应式布局 |

### 后端

| 文件 | 用途 |
|------|------|
| `backend/webapp.py` | 路由：`/` 首页、`/api/chat/stream` Agent SSE、`/api/sessions/*` 会话与文件、`/api/sessions/{id}/workspace-files` 输入输出文件树、`/api/tools` MCP 工具列表等 |
| `backend/agent_runner.py` | Web Agent 流水线（无 RAG）：计划 → 工具匹配 → MCP，结果写入 `outputspace/{slug}/` |
| `backend/web_llm.py` | Web 专用 LLM 客户端（静默流式、`stream_to_stdout`） |
| `backend/web_prompts.py` | Web 提示词（不触发 DashScope 嵌入 / 不加载 transformers） |
| `backend/plan_utils.py` | 计划过滤、从任务文本推断工具名 |
| `backend/constants.py` | 允许展示的 MCP 工具白名单 |
| `backend/session_storage.py` | 会话标题、`storage_slug`、消息历史、分享状态 |
| `backend/agent_jobs.py` | 跟踪进行中的 Agent 任务，支持 `POST .../cancel` 终止 |
| `backend/json_parse.py` | 从模型输出中提取 JSON 工具调用，避免误报解析失败 |

### 数据与工作区

- **输入文件**：`inputspace/{storage_slug}/`（用户上传的 raw、mzML、metadata.csv 等）
- **输出文件**：`outputspace/{storage_slug}/`（转换后的 mzML、峰表、注释结果等）
- **会话 DB**：`web_frontend/data/sessions.sqlite3`

右侧文件面板通过 `GET /api/sessions/{session_id}/workspace-files` 拉取上述两个目录的文件列表（相对路径、大小、修改时间）。

## 主要 API（节选）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sessions` | 会话列表 |
| GET | `/api/sessions/{id}/messages` | 消息历史 |
| POST | `/api/sessions/{id}/files` | 上传附件到 inputspace |
| GET | `/api/sessions/{id}/workspace-files` | 输入/输出文件树 |
| POST | `/api/chat/stream` | 流式对话（含 Agent + MCP） |
| POST | `/api/sessions/{id}/cancel` | 终止当前 Agent 任务 |
