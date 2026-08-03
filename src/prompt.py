from src.build_RAG_private import preload_retriever, retrive


class PromptGenerator:
    """
    V3.0 提示词生成器 — 三阶段知识驱动架构：
    1. 计划生成：RAG 检索 → 结构化计划（含预期输出和质量检查点）
    2. 工具匹配：RAG 检索 → 工具选择 + 参数填充
    3. 质量检查：RAG 检索 → 结果分析 + 异常修正建议
    4. 报告生成：RAG 检索文献 → 综合分析报告
    """

    def __init__(self, blacklist='', goal_description=None, outputspace=None,
                 PERSIST_DIR=None, SOURCE_DIR=None, similarity_top_k=5):
        self.blacklist = blacklist.split(',') if blacklist else []
        self.goal_description = goal_description
        self.outputspace = outputspace
        self.similarity_top_k = similarity_top_k

        # 预加载 RAG 检索器
        self.retriever = preload_retriever(
            PERSIST_DIR=PERSIST_DIR, SOURCE_DIR=SOURCE_DIR,
            similarity_top_k=similarity_top_k
        )

    # ==================== Phase 1: Plan Generation ====================

    def plan_prompt(self, data_list, metadata_csv, tools_info,
                    metadata_path=None, metadata_description=None,
                    run_output_dir=None, skill_context=None):
        """
        生成知识驱动的结构化计划 Prompt — V3.4。

        核心改进：
        1. 管线阶段与 paper_method_extractor_V1.py KEYWORDS 分类对齐（13 阶段）
        2. Skill + 文献平级（V3.4）：多论文共识 Skill 与单篇 RAG 文献同等优先，
           两者都可以调整/跳过/重排管线阶段；13 段清单仅为最终覆盖度检查（最低优先级）
        3. 参数优先级：Skill 共识 > RAG 文献 > 工具默认值
        4. 对比模式：文献中有多工具实验比对时，允许同阶段使用多工具交叉验证
        5. metadata_file_path 独立字段：硬路径 LLM 不可修改

        Args:
            skill_context: V3.4 — 触发器匹配的场景 Skill 全文（Markdown），
                          与 RAG 文献平级，共同决定管线设计。None 表示纯 RAG 模式。

        LLM 输出结构化计划，每步包含：
        - stage: 阶段编号和名称
        - task: 任务描述（工具名 + 做什么）
        - expected_output: 预期输出文件和指标
        - quality_check: 如何判断这一步做对了
        - mode: "standard" | "literature" | "comparison"（可选）
        """
        output_base = run_output_dir if run_output_dir else self.outputspace
        # RAG 检索：证据驱动的查询 — 问"对此类研究什么方法最合适"，而非预设管线
        rag_info = retrive(
            self.retriever,
            retriever_prompt=self._enhance_query(
                f"Global goal is {self.goal_description}. "
                f"For this type of metabolomics study (data type, sample type, research question), "
                f"what analysis methods and pipelines are recommended in the literature? "
                f"Are there any published workflows that match this exact study design? "
                f"Are there any studies that experimentally compared multiple tools for the same task "
                f"(e.g., compared XCMS vs MZmine for peak detection)? "
                f"What are the expected outputs and quality metrics for each stage?"
            )
        )

        prompt = {
            "role": "Act as a Metabolomics Expert. You are the planner of a fully automated metabolomics analysis agent.",

            "rules": [
                # ============ 规则层 -1：用户意图（绝对最高优先级 — 凌驾一切）============
                "—— USER INTENT (ABSOLUTE HIGHEST PRIORITY — OVERRIDES ALL OTHER RULES) ——",
                "The '🎯 USER INSTRUCTION' field at the TOP of this prompt is the user's direct instruction. "
                "It is the SINGLE most important input. Every rule below — skills, literature, "
                "coverage checklist — operates WITHIN the boundaries set by the user's goal. "
                "When ANY conflict arises between the user's goal and ANY other rule, "
                "THE USER'S GOAL WINS. No exceptions.",
                "",
                "PARSE the user's goal for the following constraint types BEFORE building the pipeline:",
                "",
                "0.1 SCOPE TRUNCATION: If the user specifies an endpoint (e.g., '只做到统计分析', "
                "'stop after differential analysis', '只进行到差异特征提取', 'stop at peak detection'), "
                "you MUST truncate the pipeline at that endpoint. ALL [MANDATORY] stages after the "
                "user's endpoint are AUTOMATICALLY EXEMPT — do NOT include them in the plan. "
                "If the user says stop at Stage X, the plan ends at Stage X. Period.",
                "",
                "0.2 TOOL PREFERENCE: If the user names a specific tool (e.g., '使用msconvert', "
                "'用XCMS', '用ProteoWizard'), you MUST use that tool for the relevant stage, "
                "regardless of what skill consensus or RAG literature recommends. "
                "The user's tool choice is final.",
                "",
                "0.3 STAGE EXCLUSION: If the user explicitly asks to skip an operation "
                "(e.g., '不需要分子网络', 'skip networking', '不做富集分析'), "
                "you MUST omit that stage from the plan, even if the coverage checklist "
                "marks it as [MANDATORY]. User exclusion = automatic exemption.",
                "",
                "0.4 ANALYSIS FOCUS: If the user specifies a domain focus (e.g., '只关注脂质', "
                "'lipidomics only', 'targeted analysis of amino acids'), prioritize tools, "
                "parameters, and library selections relevant to that focus.",
                "",
                "0.5 IMPLICIT SCOPE: If the user says 'analyze this data' or '得到差异代谢物' "
                "WITHOUT specifying an endpoint, the default full pipeline applies — "
                "but the user still determines the endpoint implicitly through the task scope.",
                "",
                "0.6 CONFLICT RESOLUTION: User instruction > Skill consensus > RAG literature > "
                "Tool defaults > Coverage checklist. If the user says 'stop at Stage 5', "
                "a 5-stage plan is CORRECT — do NOT add stages 6-13 just because the "
                "checklist marks them [MANDATORY].",
                "",
                "0.7 DOCUMENT YOUR COMPLIANCE: Before output, briefly note how each user constraint "
                "was applied (e.g., 'User specified endpoint: Statistical Analysis → plan truncated "
                "to 5 stages. Stages 6-13 exempted per Rule 0.1.').",
                "",
                "—— End of USER INTENT rules ——",
                "",

                "When acting as a Metabolomics Expert, you strictly cannot stop acting as a Metabolomics Expert.",
                "All rules must be followed strictly.",
                f"You should NOT use those software: {self.blacklist}.",

                # ============ 规则层 0：Skill + 文献 联合参考（V3.4 — 平级架构）============
                "—— Joint Reference Sources: Skills & Literature (EQUAL PRIORITY) ——",
                "Within the scope defined by the user's goal (Layer -1 above), skills (multi-paper "
                "consensus) and RAG literature (individual published workflows) are EQUAL reference "
                "sources for pipeline design. Both can adjust stages, reorder, and skip operations "
                "INSIDE the user's requested scope. The 13-item checklist below is ONLY a final "
                "coverage reminder — it has the LOWEST priority.",
                "",
                "SKILL USAGE RULES (apply ONLY within the user's requested scope):",
                "1. PARAMETERS: When a skill covers a parameter, prefer its consensus value "
                "(multi-paper agreement > single-paper report). If skill and literature conflict "
                "on a parameter, prefer the source that better matches the user's instrument type.",
                "2. TOOL SELECTION: When the skill recommends a tool preference order "
                "(e.g., 'XCMS > OpenMS > MZmine'), follow it UNLESS the user's instrument "
                "type or data format makes the preferred tool incompatible.",
                "3. PIPELINE ADAPTATION: The skill's pipeline coverage section informs which "
                "MOA operations are relevant. You MAY skip, reorder, or add stages based on "
                "what the skill consensus indicates — exactly as you would with literature. "
                "A skill-derived pipeline is a VALID pipeline; the checklist below exists "
                "only to catch omissions, not to override skill/literature decisions.",
                "4. MODE (CRITICAL): Skill parameters do NOT determine pipeline mode. "
                "Mode ('literature' vs 'standard') is determined by whether RAG literature "
                "provides workflow guidance for that stage, NOT by whether a skill is matched. "
                "Skill consensus parameters + mode: 'literature' is the EXPECTED combination "
                "when both sources cover the stage. Use mode: 'standard' ONLY when neither "
                "skill NOR literature covers a stage and you are using tool defaults.",
                "5. literature_source FIELD: When a stage uses skill consensus parameters AND "
                "RAG literature describes the same operation, set mode to 'literature' and "
                "list BOTH sources in literature_source: the RAG paper citation FIRST, then "
                "'MOA Skill: <name> (parameter consensus)'. If ONLY the skill covers the stage, "
                "use mode: 'standard' and cite 'MOA Skill: <name>' alone.",
                "6. If no Skill section is provided, this rule has no effect — "
                "proceed to Literature-Driven Pipeline Selection below.",

                # ============ 规则层 1：文献参考（与 Skill 平级）============
                "—— Literature-Driven Pipeline Selection (EQUAL priority with Skills) ——",
                "1. FIRST, carefully examine ALL RAG documents. Look for published analysis workflows "
                "that match the user's data type (e.g., LC-MS, GC-MS) and research goal.",
                "2. If a literature workflow EXACTLY or closely matches the user's needs: "
                "ADOPT that workflow's pipeline structure directly — its stage order, tool choices, "
                "and parameter settings. You may skip stages the literature skips and reorder stages "
                "to match the literature. Add 'mode: literature' to each step. "
                "When both skill and literature cover the same stage, skill parameters take precedence "
                "(multi-paper > single-paper), but literature's stage ordering and tool choices "
                "are equally valid. "
                "You MUST fill the 'literature_source' field with the exact citation from the RAG document "
                "(format: 'Author et al. (Year), Journal, DOI:xxx' or 'Author et al. (Year), PMID:xxx'). "
                "Extract this from the source_paper lines in the RAG documents — do NOT fabricate citations.",
                "3. If NEITHER skill NOR literature provides a matching workflow, "
                "use the coverage checklist below as a starting point to build a "
                "pipeline from tool defaults. Add 'mode: standard' to each step.",
                "4. CRITICAL MODE RULE: If the RAG documents describe ANY operation that "
                "appears in your plan, those stages MUST use mode: 'literature'. "
                "A plan where ALL stages are mode: 'standard' despite available RAG "
                "literature is INVALID. Skill parameters and literature mode are NOT "
                "mutually exclusive — combine them freely: use skill consensus parameters "
                "WITH mode: 'literature' and cite both sources in literature_source. "
                "The ONLY valid reason for ALL stages to be mode: 'standard' is when "
                "RAG retrieval returned zero matching documents.",
                "5. The mode field is MANDATORY for every stage. Every stage MUST have "
                "exactly one mode: 'literature', 'standard', or 'comparison'. "
                "Do NOT omit this field.",

                # ============ 规则层 1.5：参数选择优先级 ============
                "—— Parameter Selection Priority ——",
                "When selecting tool parameters for ANY stage, follow this priority order:",
                "(1) Skill consensus: multi-paper agreement on parameter values "
                "(e.g., 'XCMS centWave ppm=10-20 across 14 papers'). Use the consensus "
                "range midpoint unless the user's instrument type suggests a different value "
                "within the range. Cite as 'MOA Skill: <name>'.",
                "(2) RAG literature: single-paper evidence that matches the user's instrument "
                "type (e.g., UHPLC vs HPLC, Orbitrap vs Q-TOF). If the RAG document explicitly "
                "reports a parameter value, use it — especially when it matches the user's "
                "exact instrument. Cite the specific paper.",
                "(3) Tool defaults: from the 'available tools information' list. Use these "
                "ONLY when neither skill nor literature covers a parameter. "
                "Tool defaults are reasonable general-purpose values.",
                "(4) NEVER invent parameter values. Do NOT average between conflicting sources — "
                "either pick the source that best matches the user's instrument, or fall back "
                "to the tool default.",
                "When marking a stage as 'mode: literature', you MUST verify that the cited "
                "source ACTUALLY reports the parameter values you use. If the source "
                "only mentions the tool name but not its parameters, mark the stage as "
                "'mode: standard' instead and use tool defaults for parameters.",

                # ============ 规则层 2：Coverage Checklist（最低优先级 — 仅兜底）============
                "—— Coverage Checklist: 13 Common Metabolomics Operations (LOWEST PRIORITY) ——",
                "Below is a coverage checklist of operations that TYPICALLY appear in metabolomics "
                "pipelines. This is the LOWEST priority reference — use it ONLY as a final sanity "
                "check after building the pipeline from skills and literature.",
                "",
                "USER SCOPE OVERRIDE (applies BEFORE coverage check): "
                "If the user's goal specifies an endpoint or excludes stages (per Rules 0.1-0.3), "
                "ALL [MANDATORY] and [OPTIONAL] operations beyond that scope are AUTOMATICALLY EXEMPT. "
                "Do NOT add them to the plan. Do NOT question whether the user 'really needs' them. "
                "A 3-stage plan is VALID if that's what the user asked for. "
                "The coverage check below is ONLY for stages WITHIN the user's requested scope.",
                "",
                "[MANDATORY] here means: 'This operation is almost always needed — you MUST "
                "CONSIDER it. If you skip it, you need a reason.' Valid reasons to skip include: "
                "the user explicitly excluded it (Rule 0.3: automatic exemption); "
                "the user specified an earlier endpoint (Rule 0.1: automatic exemption); "
                "the skill/literature pipeline for this scenario doesn't include it; the input data "
                "already satisfies it (e.g., input is .mzML → skip format conversion); the operation "
                "is already covered by a tool in another stage.",
                "[OPTIONAL] means: include only if the data or research question calls for it.",
                "",
                "COVERAGE RULES (apply to EVERY operation below):",
                "  - A single tool can cover multiple operations. Example: data_preprocessing_xcms "
                "    covers both Peak Detection (#2) AND Peak Alignment (#5) via its built-in Obiwarp step. "
                "    If you plan to use XCMS in Stage 2, do NOT create a separate Stage for #5.",
                "    ⚠️ IMPORTANT: XCMS does NOT cover Redundant Feature Filtering (#3). "
                "    Redundant feature filtering REQUIRES a dedicated tool (redundant_feature_filtering_camera). "
                "    Do NOT merge #3 into an XCMS stage. If the pipeline needs #3, you MUST create "
                "    a separate stage using redundant_feature_filtering_camera.",
                "  - Before creating a new stage, CHECK: has this operation already been accomplished "
                "    by a tool in an earlier stage? If YES → skip it. If NO → create a stage for it.",
                "  - NEVER create an N/A stage. An N/A stage means you created a stage for an operation "
                "    already covered — that is a planning error. Instead, simply omit it.",
                "  - The resulting plan should contain ONLY stages that execute actual tools — "
                "    typically 8–10 stages, NOT a fixed 13.",
                "",
                "COVERAGE CHECKLIST:",
                "  #1 数据格式转换 (Format Conversion): .raw/.d/.wiff → .mzML [MANDATORY — skip if input is already .mzML/.mzXML]",
                "  #2 峰检测 (Peak Detection): detect chromatographic peaks → feature list [MANDATORY — skip if input is a feature table]",
                "  #3 冗余特征过滤 (Redundant Feature Filtering): merge adducts/isotopes/in-source fragments [MANDATORY]",
                "  #4 同位素识别 (Isotope Identification): identify and annotate isotopic peaks [OPTIONAL — skip if no tool is available]",
                "  #5 谱峰对齐 (Peak Alignment): align retention time across samples [MANDATORY — often covered by #2 tools like XCMS/Obiwarp]",
                "  #6 缺失值填补 (Missing Value Imputation): fill/replace missing values in feature table [MANDATORY]",
                "  #7 批次效应校正 (Batch Effect Correction): correct batch effects [OPTIONAL — skip if single batch or no batch info]",
                "  #8 统计分析 (Statistical Analysis): PCA, PLS-DA, VIP, differential metabolite screening [MANDATORY]",
                "  #9 差异特征提取 (Differential Feature Extraction): extract MS/MS spectra of significant features [MANDATORY]",
                "  #10 谱库匹配定性 (Library Matching): match experimental MS/MS against reference spectral libraries [MANDATORY]",
                "  #11 未知物定性 (De Novo Identification): identify unknowns without library matches [OPTIONAL]",
                "  #12 分子网络分析 (Molecular Networking): MS/MS similarity-based molecular families [MANDATORY]",
                "  #13 富集与通路分析 (Enrichment & Pathway Analysis): KEGG/BioCyc/Reactome enrichment [MANDATORY]",
                "",
                "AFTER writing the plan, run the coverage check: for each operation #1–#13, ask: "
                "'Is this needed for this scenario?' If a [MANDATORY] operation is not covered, "
                "verify: does the skill or literature pipeline skip it? Is the input data already "
                "past this stage? If neither reason applies → add a stage for it. "
                "If a valid reason exists → that's fine, move on.",

                # ============ 规则层 3：对比模式 ============
                "—— Multi-Tool Cross-Validation (Comparison Mode) ——",
                "If the RAG literature explicitly describes experimental comparisons between "
                "multiple tools for the SAME task (e.g., 'we compared XCMS-Centwave vs MZmine-ADAP "
                "for peak detection and found XCMS detected 15% more features'), "
                "AND all compared tools are available in the 'available tools information' list, "
                "you MAY activate comparison mode for that stage.",
                "When using comparison mode:",
                "  (a) Add '[COMPARISON]' to the stage name, e.g. 'Stage 2: Peak Detection [COMPARISON]'",
                "  (b) Create ONE plan entry PER compared tool (same stage number, different tools)",
                "  (c) Set 'mode: comparison' and add a 'comparison_group' field with a shared label "
                "      (e.g., 'peak_detection_xcms_vs_mzmine')",
                "  (d) The quality_check should include criteria for comparing results across tools "
                "      (e.g., 'XCMS should detect more features than MZmine based on literature')",
                "Comparison mode is ONLY allowed when: (1) the literature explicitly compares "
                "these tools, AND (2) all compared tools are listed as available.",

                # ============ 规则层 4：每阶段工具数量 ============
                "—— Per-Stage Tool Count ——",
                "Each stage = exactly ONE step with ONE tool, UNLESS comparison mode is activated "
                "for that stage per the rules above.",
                "Do NOT create separate steps for every tool listed within the same stage "
                "unless in comparison mode.",

                # ============ 规则层 5：分子网络 QC ============
                "—— Stage 12 (molecular networking) QC guidelines ——",
                "For molecular networking, edge count depends ENTIRELY on input data diversity "
                "and is NOT a reliable quality metric. Realistic minimums: edges ≥ 5 AND clusters ≥ 2. "
                "50–80% singleton nodes are NORMAL for chemically diverse metabolomics data. "
                "Do NOT set hard edge/node ratio thresholds (e.g., 'edges ≥ 1.5× nodes') — "
                "these are impossible to meet outside of highly homogeneous datasets. "
                "Instead, quality_check should verify: (a) all 4 core files exist "
                "(graphml, edges.csv, nodes.csv, clusters.csv), (b) graphml is valid, "
                "(c) edges > 0 if spectrum count > 5, (d) network_summary.txt contains valid statistics.",

                # ============ 规则层 6：Quality Check 字段约束 ============
                "—— Quality Check Field Constraints ——",
                "quality_check MUST only contain checks that are machine-verifiable by reading output files.",
                "Do NOT reference external tools (e.g., Cytoscape, NetworkX) that are not in 'available tools information'.",
                "Do NOT specify time thresholds (e.g., '< 10 minutes', 'per file < 5 min') — execution time depends on hardware.",
                "Do NOT use subjective criteria ('visible group clustering', 'biologically meaningful', 'good separation').",
                "ONLY use objective, quantifiable checks: file existence, file size > 0, CSV row count ranges, "
                "required column presence, numeric value ranges, error/warning absence in tool output.",

                # ============ 规则层 7：阶段编号与字段规范 ============
                "—— Stage Numbering Rules ——",
                "Stage numbers MUST be sequential unique integers starting from 1: "
                "Stage 1, Stage 2, ..., Stage N. No gaps, no duplicates.",
                "Exception: comparison mode entries MAY share the same stage number for different tools "
                "on the SAME operation (e.g., two Stage 3 entries for XCMS vs MZmine).",
                "Before outputting the plan, verify: are all stage numbers consecutive without gaps or duplicates?",
                "",
                "—— Task Field Content Rules ——",
                "The 'task' field MUST contain ONLY a concrete, executable description of what the tool does "
                "with specific file paths and parameter values.",
                "Do NOT put chain-of-thought reasoning, internal debate, reconsideration, "
                "or decision-making commentary into ANY JSON field.",
                "If you decide a stage should be OMITTED, DELETE the entire entry from the plan array — "
                "do NOT keep the entry with an empty or reasoning-filled task field.",
                "Every plan entry MUST have non-empty 'task', 'expected_output', and 'quality_check' fields.",

                # ============ 通用规则 ============
                "—— Metadata Path Rule ——",
                "The metadata_file_path field above contains the EXACT filesystem path to metadata.csv. "
                "You MUST use this exact path in all task descriptions that reference the metadata file. "
                "Do NOT modify, abbreviate, or guess the metadata path — copy it verbatim from metadata_file_path.",
                "",
                "—— FINAL MODE VERIFICATION (run before output —— only for stages within user scope) ——",
                "Before finalizing your plan, verify EVERY stage's mode field:",
                "1. This verification applies ONLY to stages within the user's requested scope. "
                "Stages excluded by user constraints (Rule 0.1/0.3) need no verification.",
                "2. Count stages with RAG literature available: if the RAG knowledge section "
                "contains documents describing metabolomics workflows, at least some stages "
                "(typically Stage 1-2: Format Conversion and Peak Detection, if within user scope) MUST use "
                "mode: 'literature' with proper citations.",
                "3. If ALL stages in your plan are mode: 'standard' but RAG documents exist → "
                "this is an ERROR. Go back and change the relevant stages to mode: 'literature'.",
                "4. Stage 1 (Format Conversion) and Stage 2 (Peak Detection) are the stages "
                "where RAG literature almost ALWAYS provides guidance. If RAG documents exist, "
                "these two stages should almost never both be mode: 'standard'. "
                "Exception: if the user specified a custom tool (Rule 0.2) and literature doesn't "
                "cover it, mode: 'standard' is acceptable for that specific stage.",
                "5. mode: 'standard' is ONLY for stages where neither skill NOR literature "
                "provides specific parameter or workflow guidance — you are building that "
                "stage from tool defaults alone.",
                "",
                "You must ONLY plan steps using tools and software from the 'available tools information' list.",
                "Read ALL RAG documents to understand every stage. Do not limit yourself to the first document only.",
                "You should only respond in JSON format with fixed format.",
                "Your JSON response should only be enclosed in double quotes and you can have only one JSON in your response.",
                "You should not write anything else except for your JSON response.",
                "You should make your answer as detailed as possible.",
                "For each step, describe what the expected output files and quality metrics should look like.",
                "For each step, describe how to verify the step was executed correctly (quality check criteria).",
            ],

            # ═══════════════════════════════════════════════════════════════
            # USER INSTRUCTION — absolute highest priority (Layer -1)
            # ═══════════════════════════════════════════════════════════════
            "🎯 USER INSTRUCTION (absolute priority — obey this FIRST, before consulting any skill, literature, or checklist)": self.goal_description,
            "input": data_list,
            "metadata_file_path": metadata_path or (metadata_csv.split(":")[0] if metadata_csv and ":" in str(metadata_csv) else None),
            "metadata_description": metadata_description or (metadata_csv.split(":", 1)[1].strip() if metadata_csv and ":" in str(metadata_csv) and len(str(metadata_csv).split(":", 1)) > 1 else "Sample metadata CSV with Sample and Group columns."),
            "outputspace": f"All output files MUST go under {output_base}/<category>/<tool_name>/.",
            "available tools information": tools_info,
            # V3.3: Skill context — injection point for trigger-matched skills (highest priority)
            # Only present when a scenario skill or tool card matched the user's goal.
            # When present, LLM must follow skill parameters before RAG literature.
            **({"🎯 Skill: Scenario-Specific Parameter Consensus & Tool Recommendations (MATCHED — equal priority with RAG literature)": skill_context}
               if skill_context else {}),
            "RAG: Pipeline methodology and tool usage guide": rag_info,

            "fixed format for JSON response": {
                "plan": [
                    {
                        "stage": "stage number and name, e.g. 'Stage 1: Format Conversion' or 'Stage 2: Peak Detection [COMPARISON]'",
                        "mode": "one of: 'literature' (adopted from RAG literature workflow), 'standard' (using preset pipeline), 'comparison' (multi-tool cross-validation)",
                        "comparison_group": "if mode=comparison: shared label linking steps that belong to the same comparison, e.g. 'peak_detection_xcms_vs_mzmine'. Omit otherwise.",
                        "literature_source": "if mode=literature: REQUIRED — exact citation from RAG document (format: 'Author et al. (Year), Journal, DOI:xxx'). Extract directly from source_paper lines. If mode=standard: omit this field.",
                        "task": "detailed description: use [exact_tool_name] to do [specific task], with input from [source] and output to [destination]",
                        "expected_output": "what files should be generated and what key metrics should be in them (e.g. number of features, file sizes, column names)",
                        "quality_check": "MACHINE-VERIFIABLE checks only. Specify: which output files must exist, expected CSV row count ranges, required columns, numeric value ranges. Do NOT use time thresholds, external tool names, or subjective criteria ('visible clustering', 'biologically meaningful'). For comparison mode: also describe how results should compare across tools."
                    }
                ]
            }
        }

        return prompt

    # ==================== Phase 2: Tool Selection & Execution ====================

    def tool_match_prompt(self, task, expected_output, tools_info, history_summary=None,
                          metadata_csv=None, previous_stage_output_dir=None,
                          run_output_dir=None):
        """
        生成工具选择 Prompt。

        RAG 检索知识库中的工具使用说明和参数选择指南，
        LLM 输出选择的工具名和参数。

        V3.3: 注入 ground_truth_paths — metadata_csv 真实路径和上游阶段实际输出目录，
        防止 LLM 幻觉文件路径。

        V3.4: run_output_dir 实现每次运行物理隔离 — 工具输出写入带时间戳的子目录。
        """
        output_base = run_output_dir if run_output_dir else self.outputspace
        # ⚠️ RAG 检索只传任务描述，不传 history_summary。
        # history_summary 包含完整执行历史（可能数千 tokens），
        # 超出 DashScope text-embedding-v2 的 2048 token 限制会导致空向量。
        rag_info = retrive(
            self.retriever,
            retriever_prompt=self._enhance_query(
                f'Global goal is {self.goal_description}. '
                f'Current sub-task is {task}. '
                f'Expected output is {expected_output}. '
                f'What tool does the literature recommend for this specific task? '
                f'What parameters, thresholds, and settings are commonly used in published studies? '
                f'Are there any study-specific considerations (e.g., instrument type, sample matrix) '
                f'that should influence tool or parameter selection?'
            )
        )

        prompt = {
            "role": "You are a Metabolomics Data Analyst specializing in LC-MS/GC-MS data processing. You have deep expertise in selecting appropriate tools and parameters for each stage of a metabolomics pipeline. You should strictly follow the rules to select the most appropriate tool and generate the most appropriate parameters for the current sub-task.",

            "rules": [
                "You should only respond in JSON format with my fixed format.",
                "Your JSON response should only be enclosed in double quotes.",
                "You should not write anything else except for your JSON response.",
                "The 'name' field in tool_call MUST exactly match one of the tool names from the 'available tools information' list.",
                "If no tool exactly matches the current sub-task, select the most functionally similar tool from the available list.",
                "You should generate only necessary and accurate arguments for the tool.",
                "—— Parameter Selection Priority ——",
                "When selecting parameters, follow this priority:",
                "(1) HIGHEST: RAG literature values that match the user's instrument type and data characteristics. "
                "Extract specific parameter values from RAG documents (e.g., ppm, peakwidth, min_cosine).",
                "(2) MEDIUM: Tool default values from 'available tools information' — use ONLY when no RAG "
                "evidence is available for that specific parameter.",
                "(3) LOWEST: General domain knowledge — do NOT invent values by averaging or compromising "
                "between conflicting sources. Either pick the best-matching source or use the tool default.",
                "You should refer to similar sample situations and examples based on the RAG information to generate the appropriate arguments.",
                "You should refer to the context information (history) to understand what input files are available and what parameters were used in previous steps.",
                "The expected output describes what should result from this step — use it to guide parameter selection.",
            ],

            "current sub-task": task,
            "expected output": expected_output,
            "context information": history_summary,
            "available tools information": tools_info,
            "RAG information": rag_info,

            "ground_truth_paths": {
                "metadata_csv": metadata_csv or "NOT PROVIDED — do NOT invent a path",
                "previous_stage_output_dir": previous_stage_output_dir or "NOT APPLICABLE — this is the first stage",
                "rule": "When a tool requires metadata_csv, you MUST use the exact path from this ground_truth_paths block. "
                        "When a tool requires input_dir and previous_stage_output_dir is set, you MUST use that exact path. "
                        "These paths are verified filesystem locations — do NOT guess, modify, or substitute them.",
            },

            "outputspace": f"All output files MUST go under {output_base}/<category>/<tool_name>/.",
            "outputspace_rules": [
                f"Every tool's output_dir MUST be {output_base}/<category>/<tool_name>/.",
                "Category mapping (MANDATORY):",
                "  Format conversion → data_conversion/",
                "  Peak detection / XCMS preprocessing → data_preprocessing/",
                "  Redundant filtering → redundant_feature_filtering/",
                "  Missing value imputation → missing_value_imputation/",
                "  Statistical analysis → statistical_analysis/",
                "  Spectral annotation → library_matching/",
                "  Molecular networking → networking/",
                "  Enrichment analysis → enrichment_analysis/",
                "  Pathway analysis → pathway_analysis/",
            ],

            "fixed format for JSON response": {
                "tool_call": {
                    "name": "exact tool name from available tools list",
                    "arguments": {
                        "...": "parameter values based on RAG knowledge and context"
                    }
                }
            }
        }

        return prompt

    # ==================== Phase 2: Quality Check ====================

    def quality_check_prompt(self, task, expected_output, quality_check_criteria,
                             tool_name, tool_args, tool_result, history_summary=None,
                             structured_result=None):
        """
        生成质量检查 Prompt。

        RAG 检索知识库中的质量控制标准，
        LLM 分析执行结果是否符合预期。

        V3.1: 接受 structured_result (dict) — 工具返回的结构化执行结果，
        包含文件列表、CSV行数/列数、摘要内容、错误告警等，QC 据此做精确判断。
        """
        # ⚠️ 同样不传 history_summary 到 RAG 检索
        rag_info = retrive(
            self.retriever,
            retriever_prompt=f'Task: {task}. Expected output: {expected_output}. '
                            f'How to evaluate the quality of this metabolomics analysis step? '
                            f'What are normal ranges for key metrics? '
                            f'What are common problems and how to fix them?'
        )

        # — 构建结构化结果摘要（如果可用）—
        structured_summary = None
        if structured_result:
            structured_summary = {
                "tool_success": structured_result.get("success", True),
                "total_files": structured_result.get("total_files", 0),
                "total_size_kb": round(structured_result.get("total_size_bytes", 0) / 1024, 1),
                "file_types": structured_result.get("file_type_counts", {}),
                "csv_summaries": structured_result.get("csv_summaries", {}),
                "summary_contents": structured_result.get("summary_contents", {}),
                "warnings": structured_result.get("warnings", []),
                "errors": structured_result.get("errors", []),
            }

        prompt = {
            "role": "You are a quality inspector for a metabolomics data analysis pipeline. "
                    "Your job is to carefully examine the execution result of a data processing step "
                    "and determine whether it succeeded and produced valid results.",

            "rules": [
                "You should only respond in JSON format with fixed format.",
                "Your JSON response should only be enclosed in double quotes.",
                "You should not write anything else except for your JSON response.",
                "You should be thorough and critical — false negatives (missed errors) waste analysis time downstream.",
                "Check ALL of the following: Were output files created? Are metrics in reasonable ranges? Any error messages?",
                "Refer to the quality_check_criteria and RAG information to judge what is normal vs abnormal.",
                "If the result is FAILED, provide specific, actionable fix suggestions — what parameter to change and to what value.",
                "If the result is FAILED, explain what went wrong and why the fix should work.",
                "—— V3.2 结构化优先判断规则（最高优先级）——",
                "You MUST base your judgment EXCLUSIVELY on the structured execution result. The raw tool output may be truncated or incomplete — NEVER use raw text to override or contradict facts from the structured result.",
                "If structured_result is provided and total_files > 0 with NO errors/warnings, the step is VERY LIKELY SUCCESSFUL — set quality_pass=true.",
                "If structured_result shows CSV files with row_count > 0 matching expected columns, this is STRONG evidence of success.",
                "The files_created list in structured_result is generated by scanning the actual filesystem — it is the ground truth. Do NOT invent missing files that actually exist.",
                "Only mark as FAILED if: errors list is non-empty, OR total_files == 0, OR critical expected files are missing, OR CSV metrics are clearly out of expected range.",
                "Do NOT mark as FAILED just because the raw tool_result text is brief or truncated — the structured_result contains the ground truth.",
                "—— 文件名模糊匹配规则 ——",
                "Tool output filenames may differ slightly from the plan's expected_output names (e.g., plan expects 'ramclust_compound_intensities.csv' but actual output is 'ramclust_compound_spectra.csv'). Check whether a functionally equivalent file exists (same extension, similar content pattern) before flagging it as missing. Slight filename differences are normal tool variants, NOT errors.",
                "—— Molecular Networking (Stage 12) specific ——",
                "For molecular_networking_gnps: if ALL expected output files exist (graphml, edges.csv, nodes.csv, clusters.csv, summary.txt) AND edges > 0 AND nodes > 0, set quality_pass=true. Low edge count is a NORMAL biological result for chemically diverse metabolomics data, NOT a tool failure. Do NOT fail this stage because of edge count or singleton ratio.",
                "—— Missing Value Imputation (Stage 6) specific ——",
                "For feature_filtering_and_missing_value_imputation_knn: if output files exist (CSV + summary.txt) AND no errors, set quality_pass=true even when 0 features were filtered or 0 values were imputed. Data with no missing values is COMPLETELY NORMAL — especially for RAMClust compound-level output where compounds are formed by merging features. 'Missing values imputed: 0' in summary is a VALID SUCCESS result, not a failure. The 'mz' and 'rt_med' columns with value 0.0 are intentional placeholders for compound-level data that has no per-feature mz/rt — do NOT flag them as errors.",
            ],

            "task description": task,
            "expected output": expected_output,
            "quality check criteria": quality_check_criteria,
            "tool called": tool_name,
            "tool arguments": tool_args,
            "tool execution result (raw)": tool_result[:1000] if structured_result is None else "(raw output suppressed — use structured execution result below as the authoritative ground truth)",
            "structured execution result": structured_summary,
            "context from previous steps": history_summary,
            "RAG: Quality standards and troubleshooting guide": rag_info,

            "fixed format for JSON response": {
                "quality_pass": "true or false — true if the step produced valid results, false if something is wrong",
                "summary": "one-sentence summary of what the tool did and what was produced",
                "key_metrics": {
                    "metric_name": "value extracted from the result (e.g. number of features detected, file count, error count)"
                },
                "issues_found": "list any problems found, empty list if none",
                "fix_suggestion": "if quality_pass is false: what parameter changes to try. If true: empty string"
            }
        }

        return prompt

    # ==================== Phase 3: Report Generation ====================

    def report_prompt(self, goal_description, history_summary, outputspace,
                       file_contents=None, data_list=None, metadata_content=None):
        """
        生成综合分析报告 Prompt。

        RAG 检索知识库中的文献和生物学知识，
        LLM 直接阅读输出文件内容，生成有数据依据的分析报告。

        Args:
            file_contents: dict — {文件路径: 文件内容}，来自 agent._collect_output_files()。
                           LLM 必须从中提取所有数值事实，不得编造。
            data_list: str — 用户输入数据的描述。
            metadata_content: str — metadata.csv 的实际内容。
        """
        rag_info = retrive(
            self.retriever,
            retriever_prompt=self._enhance_query(
                f'Goal: {goal_description}. '
                f'The analysis is complete. Now write a comprehensive report. '
                f'What biological interpretations can be drawn from these results? '
                f'What are the key metabolic pathways and their biological significance? '
                f'What are standard reporting practices for metabolomics studies? '
                f'What conclusions and follow-up recommendations are appropriate? '
                f'For each biological claim or pathway interpretation, '
                f'provide the source paper citation (Author et al., Year, Journal, DOI/PMID) '
                f'from the RAG documents. Include the full citation string exactly as it '
                f'appears in the source_paper field of each RAG document.'
            )
        )

        # —— USER EXPERIMENT CONTEXT（方案 1：防止 LLM 从文献借实验背景）——
        user_context = self._build_user_context(goal_description, data_list, metadata_content)

        # 构建文件内容区块
        files_section = ""
        if file_contents:
            files_section = "—— OUTPUT FILE CONTENTS (GROUND TRUTH) ——\n\n"
            for path, content in file_contents.items():
                files_section += f"=== {path} ===\n{content}\n\n"

        rules = [
            "Write in a professional scientific style suitable for publication or project reporting.",
            # —— 核心反幻觉规则 ——
            "—— DATA INTEGRITY RULES (ABSOLUTE PRIORITY) ——",
            "1. The 'OUTPUT FILE CONTENTS' section contains the ACTUAL pipeline results. "
            "These files are the GROUND TRUTH — they take precedence over everything else, "
            "including your prior knowledge, the execution history summary, and RAG context.",
            "2. You MUST extract ALL numerical facts EXCLUSIVELY from the output file contents. "
            "This includes: feature counts, differential metabolite counts, log2FC values, "
            "p-values, FDR-adjusted p-values, VIP scores, PLS-DA error rates, PCA variance "
            "percentages, network node/edge counts, molecular family counts, annotation rates, "
            "cosine scores, chemical class percentages, pathway enrichment p-values, "
            "and fold-enrichment scores.",
            "3. COUNT from the data — do not guess. If differential_metabolites.csv has 48 data "
            "rows, you MUST report exactly 48. If the file has 27 up-regulated and 21 "
            "down-regulated features, you MUST report those exact numbers. Read the file, "
            "count the rows, and report what you see.",
            "4. If a number or fact does NOT appear in the output file contents, write "
            "'not available in pipeline output' — NEVER fabricate, approximate, or infer it "
            "from your prior knowledge.",
            "5. The execution history summary (file counts/sizes) is METADATA about the run — "
            "it tells you whether stages succeeded. Do NOT use it as a source for biological "
            "results. Only the output file contents contain the actual data.",
            "6. KEGG compound/pathway IDs that appear literally in the files (e.g., 'C00389', "
            "'map00946') may be mapped to human-readable names using your knowledge — this is "
            "legitimate interpretation, not fabrication. But if a file only contains "
            "Spectraverse IDs (e.g., 'SPECTRAVERSE0000442240') with no common name, "
            "report the ID as-is and note that no common name was assigned.",
            # —— 方案 3：Section 1 硬约束 ——
            "—— SECTION 1 (ANALYSIS OVERVIEW) HARD CONSTRAINTS ——",
            "7. For Section 1 (Analysis Overview), you MUST describe the user's experiment "
            "using ONLY information from the 'USER EXPERIMENT CONTEXT' block above. "
            "If species, tissue type, disease model, or treatment details are not stated "
            "in the user experiment context, you MUST write 'not specified by the user' — "
            "DO NOT substitute these facts from RAG literature documents.",
            "8. RAG documents describe OTHER RESEARCHERS' experiments — their experimental "
            "contexts (cell type, animal model, disease, treatment) are METHODOLOGICAL "
            "REFERENCES ONLY and MUST NOT be copied into the user's experimental description. "
            "For example: if a RAG document says 'MRC5 human fibroblasts were treated with "
            "13C6-glucose', that is SOMEONE ELSE'S experiment — do NOT write that the user "
            "analyzed MRC5 fibroblasts unless the user experiment context explicitly says so.",
            "9. The pipeline stages (tool names, parameters) mentioned in the execution history "
            "are legitimate to describe in Section 1. The literature_source fields in the plan "
            "are explicitly marked as 'METHODOLOGY REFERENCE ONLY' — you may cite them to "
            "justify tool choices, but their experimental details are NOT the user's experiment.",
            # —— 现有规则 ——
            "Use the RAG information to provide biological context and interpretation — "
            "do NOT just list numbers.",
            "When discussing pathways, explain their biological relevance based on RAG "
            "literature knowledge.",
            "When discussing differential metabolites, explain what the up/down regulation "
            "patterns might mean biologically.",
            # —— 引用规则 ——
            "—— CITATION RULES ——",
            "10. When you use biological knowledge from RAG documents to interpret results "
            "(e.g., pathway functions, metabolite roles, disease associations), you MUST "
            "cite the source paper. Each RAG document has a 'source_paper' field containing "
            "the full citation. Use in-text citations in the format '(Author et al., Year)' "
            "within the report body.",
            "11. At the end of the report, include a 'References' section that lists all "
            "cited papers in a consistent format: 'Author et al. (Year). Journal. DOI:xxx / PMID:xxx'. "
            "Only include papers you actually cited in the report text.",
            "12. If multiple RAG documents support the same biological claim, cite up to 2-3 "
            "of the most relevant ones — do not cite-stuff.",
            "13. If a biological interpretation comes from your general knowledge (not from a "
            "specific RAG document), do NOT fabricate a citation for it. Simply state the "
            "interpretation without a reference.",
            # —— 现有规则 ——
            "Be honest about limitations and uncertainties — if a file contains placeholder "
            "values (e.g., mz=0, rt=0), note this in the report rather than silently "
            "reporting them as real measurements.",
            "Provide actionable follow-up recommendations.",
            "Structure the report with clear sections and markdown formatting.",
        ]

        prompt = {
            "role": "You are a Metabolomics Expert writing a comprehensive analysis report. "
                    "You have just completed a full metabolomics data analysis pipeline. "
                    "Your job is to synthesize ALL the results into a clear, scientifically "
                    "rigorous report. "
                    "CRITICAL: You have access to the ACTUAL OUTPUT FILES from the pipeline. "
                    "You MUST base your report on these files — they are the ground truth. "
                    "Do NOT invent numbers that are not in the files. "
                    "CRITICAL: The USER EXPERIMENT CONTEXT below is the ONLY source of truth "
                    "about the user's experiment. If it does not mention a species, tissue, "
                    "or disease, you MUST say 'not specified by the user' — do NOT borrow "
                    "these facts from RAG literature.",

            "rules": rules,

            "USER EXPERIMENT CONTEXT": user_context,
            "analysis goal": goal_description,
            "complete execution history": history_summary,
            "output directory": f"All result files are located in {outputspace}/",
            "output file contents": (
                files_section if files_section
                else "(No output files available. Report what you can from execution history.)"
            ),
            "RAG: Literature, pathway knowledge, and biological context for interpretation": rag_info,

            "report structure (follow exactly)": {
                "sections": [
                    "## 1. Analysis Overview — summary of goal, input data, and pipeline executed",
                    "## 2. Data Quality Summary — per-step quality check results, key metrics, any warnings",
                    "## 3. Statistical Analysis Results — PCA/PLS-DA findings, differential metabolites count, volcano plot summary",
                    "## 4. Metabolite Annotation Results — spectral library matching summary, compound identification statistics",
                    "## 5. Molecular Networking Results — molecular families discovered, chemical class distribution, annotation propagation",
                    "## 6. Pathway Enrichment Analysis — significantly enriched KEGG pathways, biological interpretation of each enriched pathway",
                    "## 7. Biological Interpretation — integrated analysis: what do these metabolic changes mean in the biological context of the study?",
                    "## 8. Conclusions — key findings summarized",
                    "## 9. Follow-up Recommendations — what analyses or experiments to consider next"
                ]
            }
        }

        return prompt

    def _build_user_context(self, goal_description, data_list, metadata_content):
        """构建用户实验上下文区块，作为报告的 ground truth 信源。"""
        lines = [
            "—— USER'S ACTUAL EXPERIMENT (GROUND TRUTH — DO NOT FABRICATE BEYOND THIS) ——",
            "",
            f"User's analysis goal: {goal_description}",
            "",
        ]

        if data_list:
            lines.append(f"Input data: {data_list}")
            lines.append("")

        if metadata_content:
            lines.append(f"Sample metadata (from metadata.csv):")
            lines.append("```")
            lines.append(metadata_content.strip())
            lines.append("```")
            lines.append("")

        # 分析 metadata 可提取的事实
        if metadata_content:
            try:
                header_line = metadata_content.strip().split("\n")[0]
                data_lines = [l for l in metadata_content.strip().split("\n")[1:] if l.strip()]
                n_samples = len(data_lines)
                columns = [c.strip() for c in header_line.split(",")]
                if "Group" in columns:
                    group_idx = columns.index("Group")
                    groups = {}
                    for dl in data_lines:
                        parts = [p.strip() for p in dl.split(",")]
                        if len(parts) > group_idx:
                            g = parts[group_idx]
                            groups[g] = groups.get(g, 0) + 1
                    if groups:
                        group_summary = ", ".join(f"{g} (n={c})" for g, c in groups.items())
                        lines.append(f"Extracted facts: {n_samples} samples, {len(groups)} groups: {group_summary}.")
                        lines.append("")
            except Exception:
                pass

        lines.append("⚠️ CRITICAL RULES FOR THIS REPORT:")
        lines.append("1. The above is the ONLY information about the user's experiment.")
        lines.append("2. If a fact is NOT stated above (species, tissue, disease, treatment name, etc.),")
        lines.append("   you MUST write 'not specified by the user' in the report — DO NOT substitute")
        lines.append("   it from RAG literature documents.")
        lines.append("3. RAG documents describe OTHER labs' experiments. Their cell types, animal models,")
        lines.append("   diseases, and drug treatments are METHODOLOGY REFERENCES ONLY. The fact that a")
        lines.append("   RAG paper studied 'MRC5 fibroblasts' or 'rat colon tissue' does NOT mean the")
        lines.append("   user's experiment involves those biological systems.")
        lines.append("4. You MAY use RAG for: (a) justifying tool/parameter choices, (b) interpreting")
        lines.append("   pathway enrichment results with biological knowledge, (c) suggesting follow-up")
        lines.append("   experiments based on published approaches.")
        lines.append("5. When the user's biological context is incomplete, the report should acknowledge")
        lines.append("   this gap explicitly and interpret results generically (e.g., 'the two groups")
        lines.append("   show clear metabolic separation' rather than 'the cancer group shows...').")

        return "\n".join(lines)

    # —— 中英关键词映射：代谢组学领域 ——
    _CN_EN_KEYWORDS = {
        "差异代谢物": "differential metabolites",
        "差异代谢物质": "differential metabolites",
        "代谢组学": "metabolomics",
        "数据格式转换": "format conversion raw data",
        "原始数据": "raw data",
        "质谱": "mass spectrometry",
        "注释": "annotation identification",
        "富集分析": "enrichment analysis",
        "通路": "pathway",
        "分子网络": "molecular networking",
        "峰检测": "peak detection",
        "峰对齐": "peak alignment",
        "缺失值": "missing value imputation",
        "批次效应": "batch effect correction",
        "统计分析": "statistical analysis",
        "谱库匹配": "spectral library matching",
        "未知物": "de novo identification",
        "通路分析": "pathway analysis",
    }

    def _enhance_query(self, query: str) -> str:
        """如果查询包含中文，追加英文关键词以增强跨语言 RAG 检索召回。

        DashScope text-embedding-v2 虽为多语言模型，但知识库文档 95% 为英文，
        中文查询与英文文档之间的语义匹配精度可能下降。
        此方法检测中文并按关键词追加英文翻译，提升召回率。
        """
        import re
        has_cjk = bool(re.search(r'[一-鿿]', query))
        if not has_cjk:
            return query
        en_terms = []
        for cn, en in self._CN_EN_KEYWORDS.items():
            if cn in query:
                en_terms.append(en)
        if en_terms:
            query = f"{query}\n[English keywords: {', '.join(en_terms)}]"
        return query
