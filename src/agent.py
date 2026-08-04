import os
import sys
import json
import asyncio
from datetime import datetime
from src.llm_client import LLM_Client
from src.prompt import PromptGenerator
from src.quality_checker import parse_tool_result
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from mcp.server.fastmcp import FastMCP
from src.mcp_server.server import mcp


class Tee:
    """同时输出到终端（stdout+stderr）和日志文件。

    ⚠️ 必须同时接管 stdout 和 stderr，因为 src/mcp_server/server.py
    在 import 时把 builtins.print 改成了默认写 sys.stderr，
    只重定向 stdout 会导致所有 print() 输出绕过 Tee 直接写 stderr。
    """
    def __init__(self, filepath):
        self.file = open(filepath, "w", encoding="utf-8")
        self.stdout = sys.stdout
        self.stderr = sys.stderr

    def write(self, message):
        self.stdout.write(message)
        self.file.write(message)
        self.file.flush()

    def flush(self):
        self.stdout.flush()
        self.file.flush()

    def close(self):
        self.file.close()


class Agent:
    """
    MOA V3.0 — 知识驱动代谢组学智能体

    三阶段架构：
      Phase 1: RAG 驱动结构化计划生成（含预期输出 + 质量检查点）
      Phase 2: MCP 工具执行 + 每步 LLM 质量检查 + 失败自动修正
      Phase 3: RAG 驱动综合分析报告生成
    """

    def __init__(self, data_list, goal_description,
                 metadata_csv=None, metadata_csv_path=None,
                 metadata_csv_description=None,
                 outputspace=None, PERSIST_DIR=None, SOURCE_DIR=None,
                 max_retries=3, similarity_top_k=5):
        # 基础配置
        self.data_list = data_list
        self.goal_description = goal_description

        # —— metadata_csv 兼容处理 ——
        # 新格式: metadata_csv_path + metadata_csv_description (推荐)
        # 旧格式: metadata_csv = "path: description"
        if metadata_csv_path:
            self.metadata_csv_path = metadata_csv_path
            self.metadata_csv_description = metadata_csv_description or ""
        elif metadata_csv and ":" in metadata_csv:
            # 旧冒号格式：自动拆分
            parts = metadata_csv.split(":", 1)
            self.metadata_csv_path = parts[0].strip()
            self.metadata_csv_description = parts[1].strip() if len(parts) > 1 else ""
        elif metadata_csv:
            self.metadata_csv_path = metadata_csv
            self.metadata_csv_description = metadata_csv_description or ""
        else:
            self.metadata_csv_path = None
            self.metadata_csv_description = None

        # 保留旧格式兼容性 (report_phase 等处使用)
        self.metadata_csv = metadata_csv or (
            f"{self.metadata_csv_path}: {self.metadata_csv_description}"
            if self.metadata_csv_path else None
        )
        self.outputspace = outputspace
        self.max_retries = max_retries

        # 初始化状态
        self.tasks = []          # 结构化计划列表（每项含 task/expected_output/quality_check）
        self.history_summary = []
        self.stage_results = []  # 每个阶段的结构化执行结果（供 Phase 3 动态发现输出文件）

        # 获取 MCP 工具列表
        self.tools_info = asyncio.run(self._get_all_mcp_tools_info(mcp))

        # 初始化核心组件
        self.llm_client = LLM_Client()
        self.prompt_generator = PromptGenerator(
            goal_description=self.goal_description,
            outputspace=self.outputspace,
            PERSIST_DIR=PERSIST_DIR,
            SOURCE_DIR=SOURCE_DIR,
            similarity_top_k=similarity_top_k,
        )

    # ================ MCP 工具信息 ================

    async def _get_all_mcp_tools_info(self, mcp_server: FastMCP) -> list:
        """提取 MCP server 中所有已注册工具的名称和参数信息。"""
        tools_info = await mcp_server.list_tools()
        return tools_info

    # ================ JSON 解析 ================

    def _extract_json(self, response):
        """提取响应中的 JSON 内容，自动修复 LLM 常见的 JSON 格式错误。

        LLM 经常产生不合规的 JSON 转义（如 \\'），
        这里先尝试严格解析，失败后再进行修复尝试。
        """
        start = response.find("{")
        end = response.rfind("}") + 1
        if start < 0 or end <= start:
            return {}

        json_str = response[start:end]

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # 修复 LLM 常见错误：JSON 中不允许 \\'（单引号无需转义）
            try:
                fixed = json_str.replace("\\'", "'")
                result = json.loads(fixed)
                print("   ⚠️ JSON 需修复 \\' 转义后才能解析，已自动处理。")
                return result
            except json.JSONDecodeError as e2:
                print(f"   ❌ JSON 解析失败（已尝试修复）: {e2}")
                return {}
        except Exception as e:
            print(f"   ❌ 提取 JSON 异常: {e}")
            return {}

    # ================ Skill Matching (V3.3) ================

    def _match_skill(self) -> tuple[str, list[str]]:
        """基于用户目标匹配场景 Skill + 工具参考卡（触发器优先 + RAG 兜底）。

        Returns:
            (skill_context, matched_skill_names): 注入 plan_prompt 的文本块和命中列表
        """
        import os as _os

        registry_path = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "phase2_output", "skill_registry.json"
        )
        if not _os.path.exists(registry_path):
            print("   ⚠️ Skill registry not found, skipping skill matching.")
            return "", []

        with open(registry_path, encoding="utf-8") as f:
            registry = json.load(f)

        goal_lower = self.goal_description.lower()
        matched_skills = []
        matched_tools = []

        # Phase 1: 触发器匹配 — 关键词命中即加载
        for skill in registry.get("skills", []):
            keywords = skill.get("trigger_keywords", [])
            hits = [kw for kw in keywords if kw.lower() in goal_lower]
            if hits:
                skill_file = _os.path.join(
                    _os.path.dirname(registry_path),
                    skill.get("file", "")
                )
                if _os.path.exists(skill_file):
                    content = open(skill_file, encoding="utf-8").read()
                    matched_skills.append((skill, content, hits))
                    print(f"   🎯 Skill matched: {skill.get('skill_name', skill.get('file', '?'))} "
                          f"(hits: {hits[:4]})")

        # Phase 2: 工具卡匹配 — 如果用户 query 中提到了具体工具名
        for tool in registry.get("tool_cards", []):
            tool_name = tool.get("tool_name", "").lower()
            if tool_name and tool_name in goal_lower:
                card_file = _os.path.join(
                    _os.path.dirname(registry_path),
                    tool.get("file", "")
                )
                if _os.path.exists(card_file):
                    content = open(card_file, encoding="utf-8").read()
                    matched_tools.append((tool, content))
                    print(f"   🔧 Tool card matched: {tool.get('tool_name')}")

        if not matched_skills and not matched_tools:
            print("   ℹ️  No skill matched by trigger keywords — falling back to RAG-only mode.")
            return "", []

        # 组装 skill_context
        parts = []
        skill_names = []

        if matched_skills:
            parts.append("## 🎯 Scenario Skills (Trigger-Matched — HIGHEST PRIORITY)")
            parts.append("The following curated skill documents were MATCHED by your specific "
                         "research scenario. Their parameter consensus and tool recommendations "
                         "reflect patterns extracted from multiple published papers.\n")
            for skill, content, hits in matched_skills:
                name = skill.get('skill_name', 'unknown')
                domain = skill.get('functional_domain', '')
                skill_names.append(name)
                parts.append(f"### Skill: {domain} (`{name}`)")
                parts.append(f"*Triggered by keywords: {', '.join(hits[:5])}*\n")
                # 包含完整 skill 文档
                parts.append(content)
                parts.append("\n---\n")

        if matched_tools:
            parts.append("## 🔧 Tool Reference Cards (Trigger-Matched)")
            parts.append("The following tool reference cards were matched because you mentioned "
                         "specific tools by name. Use their parameter matrices as PRIMARY source.\n")
            for tool, content in matched_tools:
                parts.append(content)
                parts.append("\n---\n")

        skill_context = "\n".join(parts)
        print(f"   📋 Skill context size: {len(skill_context)} chars")
        return skill_context, skill_names

    def plan_phase(self):
        """
        Phase 1: RAG 检索知识库 → LLM 生成结构化计划

        计划中每步包含：
        - stage: 阶段编号和名称
        - task: 详细任务描述
        - expected_output: 预期输出文件和指标
        - quality_check: 质量检查标准
        """
        print("\n" + "="*60)
        print("📋 Phase 1: 知识驱动的计划生成")
        print("="*60)

        # —— V3.3: Skill 触发器匹配 ——
        skill_context, matched_skill_names = self._match_skill()
        self.matched_skill_names = matched_skill_names

        prompt = self.prompt_generator.plan_prompt(
            data_list=self.data_list,
            metadata_csv=self.metadata_csv,
            metadata_path=self.metadata_csv_path,
            metadata_description=self.metadata_csv_description,
            tools_info=self.tools_info,
            run_output_dir=self.run_output_dir,
            skill_context=skill_context,
        )
        messages = [{"role": "user", "content": str(prompt)}]
        print("✅ 正在调用 LLM 生成结构化计划...")
        resp = self.llm_client.think(messages)

        plan_data = self._extract_json(resp)
        self.tasks = plan_data.get("plan", [])

        # —— 后处理：清理 LLM 常见错误（内心独白、空条目、重复编号）——
        original_count = len(self.tasks)
        self.tasks = self._clean_and_validate_plan(self.tasks)
        if len(self.tasks) != original_count:
            print(f"   ⚠️ 计划从 {original_count} 个条目清理为 {len(self.tasks)} 个")

        # 方案 2：标记 literature_source 为仅方法参考，防止 LLM 在报告中借用文献的实验背景
        for task in self.tasks:
            if task.get("literature_source"):
                task["literature_source"] = (
                    "⚠️ METHODOLOGY REFERENCE ONLY — this describes ANOTHER lab's experiment, "
                    "NOT the user's. Use only the tool choices and parameters from this source. "
                    "The experimental context (species, tissue, disease, treatment) belongs to "
                    "the cited paper, not to the user. Source: " + task["literature_source"]
                )

        # 记录计划到历史
        self.history_summary.append({
            "role": "user",
            "content": f"Your structured plan for {self.goal_description} is: {json.dumps(self.tasks, ensure_ascii=False)}"
        })

        print(f"✅ 计划生成完成，共 {len(self.tasks)} 个阶段/步骤")
        for i, step in enumerate(self.tasks):
            print(f"   {i+1}. [{step.get('stage', 'N/A')}] {step.get('task', 'N/A')[:80]}...")

        # 保存计划到文件（运行目录 + outputspace 根目录各一份方便查看）
        plan_file = os.path.join(self.run_output_dir, "analysis_plan.json")
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(self.tasks, f, ensure_ascii=False, indent=2)
        print(f"📄 计划已保存至: {plan_file}")

    def _clean_and_validate_plan(self, tasks):
        """对 LLM 生成的计划进行后处理验证和清理。

        处理以下 LLM 常见错误：
        1. 删除 task 字段包含内心独白/自我辩驳的条目
        2. 删除 expected_output 和 quality_check 均为空的条目
        3. 重新编排序号确保 Stage 1, 2, ..., N 连续无重复

        Returns:
            list: 清理后的计划条目列表
        """
        import re

        # 内心独白检测模式
        monologue_patterns = [
            r"So\s+Stage\s+\d+\s+is\s+omitted",
            r"this stage is\s+\*+\s*omitted",
            r"Correction:",
            r"But wait",
            r"Re-evaluating",
            r"Final plan has\s+\d+\s+stages",
            r"no\s+FBMN\s+stage",
            r"Confirmed\.",
            r"therefore.*omit",
            r"this stage is\s+\*optional\*",
        ]
        monologue_re = re.compile("|".join(monologue_patterns), re.IGNORECASE)

        cleaned = []
        removed_count = 0

        for i, entry in enumerate(tasks):
            task = entry.get("task", "").strip()
            expected = entry.get("expected_output", "").strip()
            quality = entry.get("quality_check", "").strip()

            # 条件 1：task 包含内心独白
            if monologue_re.search(task):
                stage = entry.get("stage", f"index {i}")
                print(f"   🧹 已删除 [{stage}] — task 包含 LLM 内心独白/自我辩驳")
                removed_count += 1
                continue

            # 条件 2：task 本身就是空
            if not task:
                stage = entry.get("stage", f"index {i}")
                print(f"   🧹 已删除 [{stage}] — task 为空")
                removed_count += 1
                continue

            # 条件 3：expected_output 和 quality_check 都为空
            if not expected and not quality:
                stage = entry.get("stage", f"index {i}")
                print(f"   🧹 已删除 [{stage}] — expected_output 和 quality_check 均为空")
                removed_count += 1
                continue

            cleaned.append(entry)

        # 重新编排序号
        for new_idx, entry in enumerate(cleaned):
            old_stage = entry.get("stage", "")
            # 提取阶段名称（去掉编号前缀）
            # 匹配 "Stage N: ..." 或 "Stage N - ..." 等格式
            name_match = re.match(r"Stage\s+\d+\s*[:.\-—–]\s*(.+)", old_stage)
            if name_match:
                stage_name = name_match.group(1)
            else:
                stage_name = old_stage

            new_number = new_idx + 1
            new_stage = f"Stage {new_number}: {stage_name}"
            if new_stage != old_stage:
                print(f"   🔢 重编号: [{old_stage}] → [{new_stage}]")
            entry["stage"] = new_stage

        if removed_count > 0:
            print(f"   🧹 计划清理: 删除了 {removed_count} 个无效条目，剩余 {len(cleaned)} 个阶段")

        return cleaned

    # ================ Path Validation ================

    _TOOLS_REQUIRING_METADATA = {
        "statistical_analysis_mixomics",
        "molecular_networking_fbmn",
    }

    def _validate_and_fix_tool_args(self, tool_name, tool_args):
        """在调用工具前验证并自动纠正 LLM 生成的路径参数。

        防御性检查：
        1. metadata_csv 路径：如果 LLM 生成了错误/不存在的路径，自动替换为 ground truth。
        2. input_dir 路径：如果路径不存在，尝试从上一阶段实际输出目录恢复。
        """
        corrected = {}

        # — metadata_csv 路径验证 —
        if tool_name in self._TOOLS_REQUIRING_METADATA:
            meta_arg = tool_args.get("metadata_csv")
            if self.metadata_csv_path:
                if not meta_arg or not os.path.exists(str(meta_arg)):
                    if meta_arg:
                        print(f"   ⚠️ 元数据路径不存在，已自动纠正: {meta_arg} → {self.metadata_csv_path}")
                    tool_args["metadata_csv"] = self.metadata_csv_path
                    corrected["metadata_csv"] = self.metadata_csv_path

        # — input_dir 路径验证 —
        input_dir = tool_args.get("input_dir")
        if input_dir and not os.path.exists(str(input_dir)):
            if hasattr(self, 'last_actual_output_dir') and self.last_actual_output_dir:
                if os.path.exists(self.last_actual_output_dir):
                    print(f"   ⚠️ input_dir 不存在，自动纠正: {input_dir} → {self.last_actual_output_dir}")
                    tool_args["input_dir"] = self.last_actual_output_dir
                    corrected["input_dir"] = self.last_actual_output_dir

        # — 通用路径参数存在性警告 —
        for key, val in tool_args.items():
            if isinstance(val, str) and val.startswith("/") and not os.path.exists(val):
                if key not in ("output_dir",):  # output_dir 是工具内部创建的
                    print(f"   ⚠️ 路径参数 '{key}' = '{val}' 不存在于文件系统（可能为工具内部创建）")

        if corrected:
            print(f"   ✅ 已纠正参数: {json.dumps(corrected, ensure_ascii=False)}")

    # ================ Phase 2: 带质检的工具执行 ================

    async def execution_phase(self):
        """
        Phase 2: 逐步执行计划

        每步流程：
        1. RAG 检索 → LLM 选择 MCP 工具 + 填参数
        2. 调用 MCP 工具执行
        3. RAG 检索 → LLM 质量检查
        4. 不合格 → 分析原因 → 调整参数 → 重试（最多 3 次）
        5. 合格 → 记录结果摘要，进入下一步
        """
        print("\n" + "="*60)
        print("⚙️  Phase 2: 带质检的工具执行")
        print("="*60)

        valid_tool_names = {t.name for t in self.tools_info}

        params = StdioServerParameters(
            command="python", args=["-m", "src.mcp_server.server"]
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                for step_idx, step in enumerate(self.tasks):
                    task_desc = step.get("task", "")
                    expected_output = step.get("expected_output", "")
                    quality_check_criteria = step.get("quality_check", "")
                    stage_name = step.get("stage", f"Step {step_idx+1}")

                    print(f"\n----- {stage_name} -----")
                    print(f"📌 任务: {task_desc}")

                    # 兜底检测：计划中标记为无需执行的阶段直接跳过
                    skip_markers = [
                        task_desc.strip().startswith("N/A"),
                        "no additional tool execution required" in task_desc.lower(),
                        "no tool execution required" in task_desc.lower(),
                        task_desc.strip() == "",
                    ]
                    if any(skip_markers):
                        print(f"⏭️ 阶段跳过（计划中无需工具执行）")
                        self.history_summary.append({
                            "role": "tool",
                            "content": f"Step [{stage_name}] SKIPPED — no tool execution required per plan."
                        })
                        self.stage_results.append({
                            "stage": stage_name,
                            "tool": None,
                            "task": task_desc,
                            "success": True,
                            "result": None,
                        })
                        continue

                    retry_count = 0
                    step_success = False
                    last_result = None
                    last_structured_result = None

                    while retry_count < self.max_retries and not step_success:
                        if retry_count > 0:
                            print(f"🔄 重试 {retry_count}/{self.max_retries}...")

                        # Step 2.1: 工具选择
                        tool_match_prompt = self.prompt_generator.tool_match_prompt(
                            task=task_desc,
                            expected_output=expected_output,
                            tools_info=self.tools_info,
                            history_summary=self.history_summary,
                            metadata_csv=self.metadata_csv_path,
                            previous_stage_output_dir=getattr(self, 'last_actual_output_dir', None),
                            run_output_dir=self.run_output_dir,
                        )
                        print(f"🔍 正在匹配工具...")
                        resp = self.llm_client.think(
                            [{"role": "user", "content": str(tool_match_prompt)}]
                        )
                        resp_data = self._extract_json(resp)

                        # 兼容两种格式
                        if "tool_call" not in resp_data and "name" in resp_data:
                            resp_data = {"tool_call": resp_data}

                        if "tool_call" not in resp_data:
                            print("⚠️ LLM 未返回有效 tool_call，重试...")
                            retry_count += 1
                            continue

                        tool_name = resp_data["tool_call"]["name"]

                        # 校验工具名
                        if tool_name not in valid_tool_names:
                            print(f"⚠️ 工具 '{tool_name}' 未注册，重新匹配...")
                            self.history_summary.append({
                                "role": "tool",
                                "content": f"Error: Tool '{tool_name}' is not available."
                            })
                            retry_count += 1
                            continue

                        tool_args = resp_data["tool_call"]["arguments"]

                        # —— 路径硬验证：在调用工具前纠正 LLM 幻觉的路径 ——
                        self._validate_and_fix_tool_args(tool_name, tool_args)

                        print(f"🔧 执行工具: {tool_name}")
                        print(f"   参数: {json.dumps(tool_args, ensure_ascii=False)}")

                        # Step 2.2: 执行工具
                        result = await session.call_tool(tool_name, tool_args)

                        # MCP 协议级错误（工具抛出未捕获异常时框架返回 isError=True）
                        mcp_is_error = getattr(result, 'isError', False)

                        # 提取工具返回的实际文本（MCP 封装在 result.content[0].text）
                        if hasattr(result, 'content') and result.content:
                            result_text = result.content[0].text
                        else:
                            result_text = str(result)

                        # 尝试解析结构化 JSON 返回值（V3.1+ 工具返回格式）
                        try:
                            structured_result = json.loads(result_text)
                            tool_files = structured_result.get("files_created", [])
                            tool_csv_summaries = structured_result.get("csv_summaries", {})
                            tool_summary_contents = structured_result.get("summary_contents", {})
                            tool_metrics = structured_result.get("metrics", {})
                            tool_success = structured_result.get("success", True)
                            tool_warnings = structured_result.get("warnings", [])
                            tool_errors = structured_result.get("errors", [])
                            total_files = structured_result.get("total_files", len(tool_files))
                            total_size = structured_result.get("total_size_bytes", 0)
                            file_types = structured_result.get("file_type_counts", {})
                            # 人类可读的简短摘要
                            summary_parts = [f"{total_files} files ({total_size/1024:.1f} KB)"]
                            if file_types:
                                summary_parts.append(str(file_types))
                            if tool_warnings:
                                summary_parts.append(f"⚠ {len(tool_warnings)} warnings")
                            if tool_errors:
                                summary_parts.append(f"❌ {len(tool_errors)} errors")
                            result_display = " | ".join(summary_parts)
                        except (json.JSONDecodeError, TypeError, AttributeError):
                            # 旧格式：纯文本返回值
                            structured_result = None
                            tool_files = []
                            tool_csv_summaries = {}
                            tool_summary_contents = {}
                            tool_metrics = {}
                            tool_warnings = []
                            tool_errors = []
                            total_files = 0
                            total_size = 0
                            file_types = {}
                            result_display = result_text[:200]

                            # 纯文本返回值可能是工具异常报错（如 "Error executing tool ..."），
                            # 这类错误不会被结构化 JSON 捕获，需要在此检测。
                            if result_text.strip().lower().startswith("error"):
                                tool_success = False
                                tool_errors.append(result_text.strip()[:200])
                            else:
                                tool_success = True

                        print(f"📤 工具返回: {result_display}")
                        last_structured_result = structured_result

                        # ============================================================
                        # Step 2.3: 质量检查 [暂时禁用 — 2026-07-21]
                        #   QC LLM 频繁产生幻觉和假阳性误判（原始文本截断、
                        #   结构化结果被忽略、文件名模糊匹配失败等），
                        #   导致 pipeline 不必要的重试和跳过。
                        #   暂以 structured_result 的硬事实替代 LLM 判断。
                        #   恢复时取消下面注释并删除 bypass 赋值即可。
                        # ============================================================
                        #
                        # qc_prompt = self.prompt_generator.quality_check_prompt(
                        #     task=task_desc,
                        #     expected_output=expected_output,
                        #     quality_check_criteria=quality_check_criteria,
                        #     tool_name=tool_name,
                        #     tool_args=tool_args,
                        #     tool_result=result_text,
                        #     history_summary=self.history_summary,
                        #     structured_result=structured_result,
                        # )
                        # print(f"🔎 正在进行质量检查...")
                        # qc_resp = self.llm_client.think(
                        #     [{"role": "user", "content": str(qc_prompt)}]
                        # )
                        # qc_data = self._extract_json(qc_resp)
                        #
                        # quality_pass = str(qc_data.get("quality_pass", "false")).lower() == "true"
                        # qc_summary = qc_data.get("summary", "")
                        # issues = qc_data.get("issues_found", [])
                        # fix_suggestion = qc_data.get("fix_suggestion", "")
                        # key_metrics = qc_data.get("key_metrics", {})

                        # — QC bypass —
                        quality_pass = True
                        qc_summary = "QC disabled — tool execution completed."
                        issues = []
                        fix_suggestion = ""
                        key_metrics = {
                            "total_files": total_files,
                            "total_size_kb": round(total_size / 1024, 1),
                        }
                        if tool_errors:
                            quality_pass = False
                            qc_summary = f"Tool reported {len(tool_errors)} error(s)"
                            issues = tool_errors
                        elif mcp_is_error:
                            quality_pass = False
                            qc_summary = "MCP reported tool error (isError=True)"
                            issues = [result_text[:200]]

                        # —— 文件系统交叉验证 ——
                        # 基于 structured_result 中的 files_created 列表，
                        # 用 os.path.exists() 验证关键文件确实存在于磁盘上。
                        # 这是硬检查，防止 structured_result 声称文件存在但实际不存在。
                        fs_verified = {"total_files_on_disk": 0, "all_files_exist": True, "missing_files": []}
                        if structured_result and tool_files:
                            actual_count = 0
                            for f in tool_files:
                                fpath = os.path.join(f.get("directory", ""), f.get("path", ""))
                                if fpath and os.path.exists(fpath):
                                    actual_count += 1
                                else:
                                    fs_verified["missing_files"].append(f.get("path", ""))
                            fs_verified["total_files_on_disk"] = actual_count
                            fs_verified["all_files_exist"] = (actual_count == len(tool_files))
                            if not fs_verified["all_files_exist"]:
                                quality_pass = False
                                qc_summary = f"Filesystem verification failed: {actual_count}/{len(tool_files)} files exist on disk"
                                issues.append(f"Missing on disk: {fs_verified['missing_files']}")
                            key_metrics["files_on_disk"] = actual_count
                            key_metrics["files_reported"] = len(tool_files)
                        print(f"🔎 QC bypassed — assuming pass (errors={len(tool_errors)}, mcp_is_error={mcp_is_error}, files={total_files}, fs_verified={fs_verified['total_files_on_disk']}/{len(tool_files) if tool_files else 0})")

                        if quality_pass:
                            print(f"✅ 质量检查通过 | {qc_summary}")
                            if key_metrics:
                                print(f"   📊 关键指标: {json.dumps(key_metrics, ensure_ascii=False)}")
                            step_success = True
                            last_result = result_text

                            # —— 记录实际路径到 last_actual_output_dir（供下一阶段 tool_match_prompt 使用）——
                            actual_output_dir = tool_args.get("output_dir", "")
                            if actual_output_dir:
                                self.last_actual_output_dir = actual_output_dir

                            # 提取关键输入路径
                            input_paths = {k: v for k, v in tool_args.items()
                                          if k in ("input_dir", "input_mgf", "input_feature_table",
                                                   "input_csv", "differential_csv", "metadata_csv")}

                            # 记录成功结果（使用结构化摘要 + 关键指标 + 实际文件路径）
                            history_result_preview = result_display
                            history_content = (
                                f"Step [{stage_name}] SUCCESS. "
                                f"Tool: {tool_name}. Summary: {qc_summary}. "
                                f"Metrics: {json.dumps(key_metrics, ensure_ascii=False)}. "
                                f"Actual output_dir: {actual_output_dir}. "
                                f"Actual inputs: {json.dumps(input_paths, ensure_ascii=False)}. "
                                f"Result: {history_result_preview}"
                            )
                            self.history_summary.append({
                                "role": "tool",
                                "content": history_content
                            })
                        else:
                            print(f"❌ 质量检查未通过 | {qc_summary}")
                            if issues:
                                print(f"   ⚠️ 发现问题: {issues}")
                            if fix_suggestion:
                                print(f"   💡 修正建议: {fix_suggestion}")

                            # 记录失败并注入修正建议
                            self.history_summary.append({
                                "role": "tool",
                                "content": f"Step [{stage_name}] FAILED quality check. "
                                           f"Tool: {tool_name}. Issues: {issues}. "
                                           f"Fix suggestion: {fix_suggestion}. "
                                           f"Result: {result_text[:500]}"
                            })

                            # 将修正建议注入历史，帮助 LLM 在重试时调整参数
                            if fix_suggestion:
                                self.history_summary.append({
                                    "role": "user",
                                    "content": f"Previous attempt failed. Please adjust parameters based on this suggestion: {fix_suggestion}"
                                })

                            retry_count += 1
                            continue

                    if not step_success:
                        print(f"⚠️ 步骤 '{stage_name}' 在 {self.max_retries} 次重试后仍未通过质检，记录并继续。")
                        self.history_summary.append({
                            "role": "tool",
                            "content": f"Step [{stage_name}] SKIPPED after {self.max_retries} failed attempts. Last result: {last_result}"
                        })

                    # 存储阶段结构化结果（供 Phase 3 报告动态发现文件）
                    self.stage_results.append({
                        "stage": stage_name,
                        "tool": tool_name,
                        "task": task_desc,
                        "success": step_success,
                        "result": last_structured_result,
                    })

        print(f"\n✅ Phase 2 执行完成，共处理 {len(self.tasks)} 个步骤")

    # ================ Phase 3: 报告生成 ================

    def _collect_output_files(self):
        """基于已执行工具的结构化结果，动态收集报告相关的输出文件内容。

        不再硬编码文件名。遍历 Phase 2 存储的每个阶段的结构化执行结果：
        1. summary_contents — 直接使用（_format_tool_result 已捕获 *_summary.txt 内容）
        2. CSV 文件 — 根据行数智能读取（小文件全量，大文件截断）
        3. 小文本文件（.txt, .log ≤ 10KB）— 补充读取摘要遗漏的文本文件
        4. 跳过二进制文件（GraphML, MGF, PNG, PDF 等）

        Returns:
            dict: {"[stage_name] relative_path": 文件内容}
        """
        if not self.stage_results:
            return {}

        file_contents = {}
        # 阈值配置
        max_csv_full_rows = 100       # ≤100 行：全量读取
        max_csv_partial_rows = 500    # 101~500 行：读前 50 行
        csv_partial_limit = 50        # 中等文件截断行数
        csv_brief_limit = 10          # 大文件截断行数
        small_text_max_bytes = 10 * 1024  # 10KB

        # 去重：按 (文件名, 内容前200字符) 签名避免重复文件
        seen_signatures = set()

        # 无报告价值的文件名模式
        skip_patterns = ("sessioninfo",)

        for sr in self.stage_results:
            stage_name = sr.get("stage", "Unknown")
            result = sr.get("result")
            if not result or not isinstance(result, dict):
                continue

            # —— 1. Summary 文件（_format_tool_result 已捕获前 3000 字符） ——
            for relpath, content in result.get("summary_contents", {}).items():
                if not content or not isinstance(content, str):
                    continue
                sig = (os.path.basename(relpath), content[:200])
                if sig in seen_signatures:
                    continue
                seen_signatures.add(sig)
                file_contents[f"[{stage_name}] {relpath}"] = content

            # —— 2. CSV 文件 ——
            csv_summaries = result.get("csv_summaries", {})
            files_created = result.get("files_created", [])

            # 构建 path → directory 查找表
            path_to_dir = {}
            csv_paths_seen = set()
            for f in files_created:
                p = f.get("path", "")
                d = f.get("directory", "")
                if p and d:
                    path_to_dir[p] = d

            for relpath, csv_info in csv_summaries.items():
                directory = path_to_dir.get(relpath)
                if not directory:
                    # 回退：模糊匹配（处理路径前缀差异）
                    for f in files_created:
                        fp = f.get("path", "")
                        if fp == relpath or fp.endswith("/" + relpath) or relpath.endswith("/" + fp):
                            directory = f.get("directory", "")
                            relpath = fp  # 使用精确路径
                            break

                if not directory:
                    continue

                filepath = os.path.join(directory, relpath)
                if not os.path.isfile(filepath):
                    continue

                row_count = csv_info.get("row_count", 0)
                try:
                    with open(filepath, encoding="utf-8", errors="replace") as fh:
                        if row_count <= max_csv_full_rows:
                            content = fh.read()
                        elif row_count <= max_csv_partial_rows:
                            lines = [next(fh, "") for _ in range(csv_partial_limit)]
                            content = "".join(lines)
                            content += (
                                f"\n... [truncated: {row_count} total rows, "
                                f"{csv_partial_limit} shown]"
                            )
                        else:
                            lines = [next(fh, "") for _ in range(csv_brief_limit)]
                            content = "".join(lines)
                            content += (
                                f"\n... [truncated: {row_count} total rows, "
                                f"{csv_brief_limit} shown]"
                            )
                    # 去重
                    sig = (os.path.basename(relpath), content[:200])
                    if sig in seen_signatures:
                        continue
                    seen_signatures.add(sig)

                    file_contents[f"[{stage_name}] {relpath}"] = content
                    csv_paths_seen.add(relpath)
                except Exception as e:
                    file_contents[f"[{stage_name}] {relpath}"] = f"[Error reading file: {e}]"

            # —— 3. 补充小文本文件（摘要遗漏的，如 plsda_cv_results.txt） ——
            summary_paths = set(result.get("summary_contents", {}).keys())
            for f in files_created:
                fpath = f.get("path", "")
                directory = f.get("directory", "")
                size = f.get("size_bytes", 0)

                if not directory or not fpath:
                    continue
                # 跳过已处理的
                if fpath in summary_paths or fpath in csv_paths_seen:
                    continue
                # 跳过无报告价值的文件
                fname_lower = os.path.basename(fpath).lower()
                if any(p in fname_lower for p in skip_patterns):
                    continue

                ext = os.path.splitext(fpath)[1].lower()
                if ext in (".txt", ".log") and 0 < size <= small_text_max_bytes:
                    filepath = os.path.join(directory, fpath)
                    if not os.path.isfile(filepath):
                        continue
                    try:
                        with open(filepath, encoding="utf-8", errors="replace") as fh:
                            content = fh.read()
                        sig = (os.path.basename(fpath), content[:200])
                        if sig in seen_signatures:
                            continue
                        seen_signatures.add(sig)
                        file_contents[f"[{stage_name}] {fpath}"] = content
                    except Exception:
                        pass

            # —— 4. 执行错误 ——
            errors = result.get("errors", [])
            if errors:
                file_contents[f"[{stage_name}] __execution_errors__"] = (
                    "\n".join(str(e) for e in errors)
                )

        if file_contents:
            data_files = sum(
                1 for k in file_contents
                if not k.endswith("__execution_errors__")
            )
            print(f"📂 已从 {len(self.stage_results)} 个阶段收集 {data_files} 个文件/摘要用于报告生成")
        return file_contents

    def report_phase(self):
        """
        Phase 3: 直接读取输出文件 → LLM 生成综合分析报告

        报告包含：
        - 分析概览
        - 数据质量总览
        - 统计分析结果
        - 代谢物注释结果
        - 分子网络结果
        - 通路富集分析
        - 生物学意义解读
        - 结论和后续建议
        """
        print("\n" + "="*60)
        print("📝 Phase 3: 生成综合分析报告")
        print("="*60)

        # 收集输出文件内容作为 LLM 的事实依据
        file_contents = self._collect_output_files()

        # 读取 metadata CSV 的实际内容（方案 1：作为报告的 ground truth 信源）
        metadata_content = None
        if self.metadata_csv_path and os.path.exists(self.metadata_csv_path):
            try:
                metadata_content = open(self.metadata_csv_path, "r", encoding="utf-8").read()
            except Exception:
                pass

        report_prompt = self.prompt_generator.report_prompt(
            goal_description=self.goal_description,
            history_summary=self.history_summary,
            outputspace=self.run_output_dir,
            file_contents=file_contents,
            data_list=self.data_list,
            metadata_content=metadata_content,
        )

        print("✅ 正在调用 LLM 生成报告（含输出文件 + 文献知识背景）...")
        messages = [{"role": "user", "content": str(report_prompt)}]
        report_content = self.llm_client.think(messages)

        # 保存报告（处理 LLM 返回 None 的情况）
        report_path = os.path.join(self.run_output_dir, "analysis_report.md")
        if report_content:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_content)
            print(f"\n📄 分析报告已保存至: {report_path}")
        else:
            print(f"\n⚠️ LLM 返回空响应，跳过报告生成。")
            # 至少写一个占位报告
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(f"# Analysis Report\n\n⚠️ Report generation failed — LLM returned empty response.\n\n"
                        f"Goal: {self.goal_description}\n\nOutput directory: {self.run_output_dir}\n")
            print(f"📄 占位报告已保存至: {report_path}")

        return report_content or ""

    # ================ Run Summary (Cross-Run Memory) ================

    def _save_run_summary(self):
        """保存结构化运行总结，供跨运行学习和经验借鉴。

        每次运行结束后自动记录：
        - 运行元信息（ID、时间、目标）
        - 计划摘要（阶段列表、模式、文献来源）
        - 工具使用记录（工具名、成功/失败、关键参数）
        - 错误和重试情况
        - 关键结果指标

        总结文件存储在 outputspace/.run_history/ 下，
        供未来的 plan_prompt 通过 RAG 或直接检索借鉴历史经验。
        """
        import json
        from datetime import datetime

        # —— 从 stage_results 和 history_summary 提取工具使用记录 ——
        tool_usage = []
        for sr in self.stage_results:
            stage = sr.get("stage", "Unknown")
            tool_name = sr.get("tool")
            success = sr.get("success", False)
            result = sr.get("result")

            usage = {
                "stage": stage,
                "tool": tool_name,
                "success": success,
            }

            if result and isinstance(result, dict):
                usage["total_files"] = result.get("total_files", 0)
                errors = result.get("errors", [])
                warnings = result.get("warnings", [])
                usage["errors"] = errors
                usage["warnings_count"] = len(warnings)

            tool_usage.append(usage)

        # —— 从 history_summary 提取关键结果指标 ——
        key_results = {}
        for entry in self.history_summary:
            content = entry.get("content", "")
            if isinstance(content, str) and "Metrics:" in content:
                try:
                    metrics_start = content.index("Metrics:") + len("Metrics:")
                    metrics_str = content[metrics_start:].split(".")[0].strip()
                    metrics = json.loads(metrics_str)
                    key_results.update(metrics)
                except (ValueError, json.JSONDecodeError):
                    pass

        # —— 计算整体统计 ——
        total_stages = len(self.stage_results)
        successful_stages = sum(1 for sr in self.stage_results if sr.get("success"))
        failed_stages = total_stages - successful_stages
        all_tool_names = [sr.get("tool") for sr in self.stage_results if sr.get("tool")]

        summary = {
            "run_id": os.path.basename(self.run_output_dir),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "goal": self.goal_description,
            "plan_summary": [
                {
                    "stage": t.get("stage", ""),
                    "mode": t.get("mode", "standard"),
                    "tool_hint": t.get("task", "")[:120],
                    "literature_source": t.get("literature_source", "")[:200] if t.get("literature_source") else None,
                }
                for t in self.tasks
            ],
            "statistics": {
                "total_stages": total_stages,
                "successful": successful_stages,
                "failed": failed_stages,
                "tools_used": list(dict.fromkeys(all_tool_names)),  # 去重保留顺序
            },
            "tool_usage": tool_usage,
            "key_results": key_results,
            "user_feedback": None,  # 预留：未来可让用户在报告末尾标注反馈
        }

        # —— 写入 .run_history/ 目录 ——
        history_dir = os.path.join(self.outputspace, ".run_history")
        os.makedirs(history_dir, exist_ok=True)
        summary_path = os.path.join(history_dir, f"{summary['run_id']}_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"📊 运行总结已保存至: {summary_path}")

    # ================ Main Entry ================

    def run(self):
        """主执行入口 — 三阶段流水线。

        V3.4: 每次运行创建带时间戳的独立子目录 (run_output_dir)，
        实现物理隔离，彻底防止跨实验数据串扰。

        V3.5: 运行结束后自动保存结构化运行总结到 .run_history/，
        供跨运行经验借鉴。
        """
        # ---- 创建本次运行的独立输出目录 ----
        os.makedirs(self.outputspace, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_output_dir = os.path.join(self.outputspace, f"run_{timestamp}")
        os.makedirs(self.run_output_dir, exist_ok=True)

        # ---- 设置日志：同时输出到终端和文件 ----
        log_path = os.path.join(self.run_output_dir, f"run_log_{timestamp}.txt")
        tee = Tee(log_path)
        sys.stdout = tee
        sys.stderr = tee

        try:
            print("\n" + "🚀"*20)
            print("MOA V3.0 — 知识驱动代谢组学智能体")
            print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"运行目录: {self.run_output_dir}")
            print(f"日志文件: {log_path}")
            print("目标: " + self.goal_description)
            print("🚀"*20)

            # Phase 1: 计划生成
            self.plan_phase()

            # Phase 2: 执行 + 质检
            asyncio.run(self.execution_phase())

            # Phase 3: 报告生成
            self.report_phase()

            # V3.5: 保存运行总结
            self._save_run_summary()

            print("\n" + "🎉"*20)
            print(f"🎉 全流程分析完成！")
            print(f"   📂 运行目录: {self.run_output_dir}")
            print(f"   📄 分析报告: {os.path.join(self.run_output_dir, 'analysis_report.md')}")
            print(f"   📋 执行计划: {os.path.join(self.run_output_dir, 'analysis_plan.json')}")
            print(f"   📝 运行日志: {log_path}")
            print("🎉"*20)

        except Exception as e:
            print(f"\n❌ 任务中断: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            sys.stdout = tee.stdout
            sys.stderr = tee.stderr
            tee.close()
            print(f"📝 日志已保存至: {log_path}")
