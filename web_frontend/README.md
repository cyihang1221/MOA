# MassAgent 网页前端

本目录是 **A/B/C 编排器**：一个会话完成上传 → 计划评审 → 执行 → 出图/报告。用户不必切换三个聊天窗口。

```
上传 + 分析目标
  → Agent A 写出 analysis_plan.md（停在待确认）
  → 用户回复「确认计划」
  → Agent B 按锁定计划调用 MCP
  → Agent C 自动出图并写 final_report.md / final_report.pdf
  → 完成后可改图 / 拼图 / 修订报告
```

未确认计划不会启动分析（需求 AC-2）。改图/拼图只在完成后进行。

## 目录结构

```
web_frontend/
├── index.html              # 单页应用入口（会话侧栏 + 聊天 + 文件面板）
├── static/
│   ├── app.js              # 前端逻辑：会话、消息、SSE、附件、文件列表
│   └── styles.css          # 页面样式与三栏布局
├── backend/
│   ├── webapp.py           # FastAPI 应用、REST/SSE API、静态资源挂载
│   ├── workflow.py         # 会话阶段与聊天路由（确认闸门）
│   ├── agent_intent.py     # 话术分类（规划/执行/出图/改图）
│   ├── agent_a/            # 把步骤列表写成可评审的 analysis_plan.md
│   ├── agent_c/            # 出图、报告
│   ├── agent_runner.py     # mode=plan 只规划；mode=execute 按锁定计划跑 MCP
│   ├── literature_rag.py   # softwares_database(_RAG) 文献检索
│   ├── session_storage.py  # SQLite 会话/消息持久化
│   ├── agent_jobs.py       # 后台任务与取消（终止生成）
│   └── json_parse.py       # Agent 输出中的 JSON / tool_call 解析
├── data/
│   └── sessions.sqlite3    # 会话数据库（运行时自动创建）
└── README.md               # 本说明
```

启动入口是 `web_frontend.backend.webapp:app`。`src/webapp.py` 仍是旧拷贝，请不要用它启动。

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
| `backend/webapp.py` | 聊天按阶段编排 A/B/C；会话含 `workflow_status` |
| `backend/workflow.py` | 确认闸门与阶段路由 |
| `backend/agent_a/` | 写出可评审的 `analysis_plan.md` |
| `backend/agent_c/` | 出图与报告；B 成功后由编排器调用 |
| `backend/agent_runner.py` | `mode=plan` 停在确认；`mode=execute` 按锁定计划跑 MCP |
| `backend/literature_rag.py` | 接入 `softwares_database_RAG`（向量）与 `softwares_database`（关键词回退） |
| `backend/web_llm.py` | Web 专用 LLM 客户端（静默流式、`stream_to_stdout`） |
| `backend/web_prompts.py` | Web 提示词；可注入 `literature_context`（文献检索结果） |
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
| POST | `/api/chat/stream` | 流式对话：改图/拼图、Agent C 出图/报告，或把计算交接给 B |
| POST | `/api/sessions/{id}/cancel` | 终止当前 Agent 任务 |
| GET | `/api/agent-c/contract` | Agent C 与 A/B 的字段契约 |
| POST | `/api/agent-c/parse-plan` | 解析 `analysis_plan.md` / JSON |
| POST | `/api/agent-c/inventory` | 清点 B 的结果目录中可出图数据 |
| POST | `/api/agent-c/run` | 按方案出图并写 `final_report.md` / `.pdf` |
| POST | `/api/sessions/{id}/agent-c/run` | 对当前会话 outputspace 跑 C |

### Agent C（给 A/B 直接调用）

规划智能体 A、执行智能体 B 不必走聊天会话。Python：

```python
from web_frontend.backend.agent_c import run_agent_c, parse_plan, inventory_results

manifest = run_agent_c(
    plan="path/to/plan_20260101.json",   # MassOmics PlanDocument
    # plan="path/to/analysis_plan.md",   # Web FR-2 或 MassOmics Markdown
    results_dir="path/to/analysis_results",
    output_dir="path/to/agent_c_output",  # 可选
    metadata_csv="path/to/metadata.csv",  # PCA 需要
    figure_mode="plan",  # plan | available | plan_then_available
)
```

产出：`figures/`、`final_report.md`、`final_report.pdf`、`agent_c_manifest.json`。契约见 `GET /api/agent-c/contract`（v1.1）。

**命令行（本地手动测试）**：

```bash
cd /path/to/agent_py_V2.0

# 按 session 短 id + 指定历史方案（dry-run 先看路径与 inventory）
python -m web_frontend.backend.agent_c \
  --session 0de4a588 \
  --plan plan_20260826_102858.md \
  --dry-run

# 正式跑 C（默认 figure_mode=plan，不加 --use-llm 则跳过深度解读）
python -m web_frontend.backend.agent_c \
  --session 0de4a588 \
  --plan plan_20260826_102858.md

# 或直接传 results_dir
python -m web_frontend.backend.agent_c \
  --results-dir "outputspace/（dbj）对上传的mzml文件进行分析，包括xc…_0de4a588" \
  --plan plan_20260826_102858.md
```

**A 方案输入（三选一）**：
- MassOmics `PlanDocument` JSON：`goal` + `steps[]` + `visualizations[]` + `interpretations[]` + `report{}`
- Web FR-2：`analysis_plan.json` / `.md`（`objective` + `required_visualization[]`）
- 旧版阶段列表：`plan[]`（由步骤文本推断图型）

B 的结果目录放入 `pca_scores.csv`、`volcano_results.csv` 等已注册数据文件；MassOmics 图中 `source_step` 会挂接对应 Step 的 `output_filename` 以优先匹配。

### 聊天按阶段路由

| 阶段 | 用户话术 | 行为 |
|------|----------|------|
| 等待输入 | 描述分析目标 | Agent A 出计划，停在待确认 |
| 待确认 | 「确认计划」 | Agent B 执行，成功后自动 C |
| 待确认 | 「开始分析 / 跑 XCMS」 | **拒绝**，提示先确认 |
| 待确认 | 修改意见 | Agent A 修订计划 |
| 已完成 | 改标题/拼图 | 本地改图/拼图 |
| 已完成 | 写报告 | 只跑 Agent C |
| 规划未完成 | 改图 | 拒绝，提示先走完执行 |

HTTP 路径必须在项目根下。缺数据的图在清单里标 `missing_data`。

