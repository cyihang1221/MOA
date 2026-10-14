# 根目录 `web_frontend` 代码区块

本目录是 **测试用编排器**（先在仓库根改、测通后再拷到 `MassOmics-Agent/MassOmics-Agent/web_frontend/`）。
网页只编排三个独立智能体，不把 A/B/C 合成 `main.py` 那条同进程流水线。

## 当前 ABC 落点（complete）

| 角色 | 真正干活的代码 | 网页侧适配 | 说明 |
|------|----------------|------------|------|
| **A 规划** | complete 树的 `plan/` | `backend/agent_a/` | 写出 `plan_*.json` + `analysis_plan.md`，停在待确认 |
| **B 执行** | 同一棵树的 `src/` + `agent_b/` | `backend/agent_b/` | 独立进程跑 `execute_plan`；工具走同仓 MCP stdio |
| **C 出图/报告** | **本目录** `backend/agent_c/` | 编排器在 B 成功后调用 | 不跑 XCMS；不用 complete 自带的 CLI `agent_c/`（测通前） |
| **编排** | `backend/webapp.py` 等 | 本目录 | 上传 → 计划评审 → 执行 → 出图 |

默认 complete 同根探测顺序见 `backend/agent_backends.py`：优先干净 worktree **`MassOmics-Agent-B`**（`origin/complete` / `MOA_completeV0.1`），其次嵌套 `MassOmics-Agent/MassOmics-Agent`。

不要改师兄 `plan/`、`src/executor.py`，除非明确要求。

## 仓库里几棵树（避免混用）

| 路径 | Git | 用途 |
|------|-----|------|
| `MassOmics-Agent-B` | 干净 `origin/complete`（`20890f7 MOA_completeV0.1`） | **默认 A+B 代码根** |
| `MassOmics-Agent/MassOmics-Agent` | `cyh` 已 merge `origin/complete`（`184010c`）：后端 complete，`web_frontend/` 与 `agent_c/` 仍为原 cyh | 测通前不要把根目录网页拷进去；未 push |
| 仓库根 `agent_a/` `agent_b/` `agent_c/`、`src/` | 旧单仓残留 | 不是 complete；`WEB_AGENT_B_BACKEND=local` 才会碰到根 `src/mcp_server` |
| 本目录 | 编排器 + 网页 C | 当前工作区 |

## `backend/` 按职责（文件先不搬家，只分区）

物理路径保持原样，避免一次改 70+ 处 import。对照下面找文件。

### 1. 编排器（用户会话）

`webapp.py` `workflow.py` `chat_router.py` `agent_intent.py` `agent_jobs.py` `agent_runner.py` `abc_run.py` `abc_contract.py` `agent_backends.py` `session_storage.py` `session_metadata.py` `session_file_resolver.py` `constants.py` `json_parse.py` `web_llm.py` `web_prompts.py` `llm_security.py` `anti_hallucination.py`

### 2. Agent A 适配

`agent_a/`（`massomics_planner.py`、`plan_document.py`、`plan_catalog.py`、`figure_blueprint.py`）  
`skill_match.py` `plan_utils.py` `analysis_intent.py`

### 3. Agent B 适配

`agent_b/`（`massomics_executor.py`、`execute_cli.py`、`plan_normalize.py`、`plan_locate.py`、`artifact_bridge.py`、`b_imports.py`）

**仅** `WEB_AGENT_B_BACKEND=local` 时用的本仓计算入口（不是网页 C）：

`tool_runner.py` `tool_registry.py` `tool_args_normalizer.py` `tool_fallback.py` `xcms_preprocess_runner.py` `xcms_patched_run.py` `mixomics_runner.py` `feature_filter_runner.py` `pipeline_utils.py`

### 4. Agent C（出图、报告、改图/拼图）

`agent_c/`（runner、figure pipeline、report、`nature_distill/`）  
完成后迭代：`plot_edit_*.py` `plot_renderer.py` `plot_data_contract.py` `plot_fonts.py` `plot_versioning.py` `generic_plot_edit.py` `semantic_plot_renderer.py` `visual_*.py` `image_merge_*.py` `export/` `paper_plot_helpers.py` `literature_*.py`

C **禁止**调用 XCMS / mixOmics 等分析工具。

### 5. 前端静态资源

`index.html` `static/app.js` `static/styles.css` `static/i18n.js`（根上若还有一份 `app.js`，以 `static/` 为准）

## 启动（本目录）

在 **仓库根** `agent_py_V2.0`：

```bash
python -m uvicorn web_frontend.backend.webapp:app --host 0.0.0.0 --port 8010
```

确认探测：`GET /api/agent-backends` 里 `layout` 应为 `complete_unified`，`massomics_root` 与 `massomics_b_root` 相同。

complete 把 `src/tool_catalog.json` 和 `data/kb/workflows.json` 放进了 Git LFS。`MassOmics-Agent-B` 若用 `GIT_LFS_SKIP_SMUDGE=1` 检出，这两个文件只是指针，**B 无法规范化计划**。拉实体（不要整库 LFS）：

```bash
cd MassOmics-Agent-B
git lfs pull --include="src/tool_catalog.json,data/kb/workflows.json"
```

不要随便 pull `softwares_database_RAG` 里的大 json。
