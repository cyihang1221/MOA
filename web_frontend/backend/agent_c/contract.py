"""Agent C（可视化与报告）与 A/B 的接口契约。

A 输出分析方案，B 输出结果目录，C 只消费这两份输入，不改 A/B 规划或计算。

契约版本：1.0
"""
from __future__ import annotations

CONTRACT_VERSION = "1.1"
CONTRACT_ID = "massagent.agent_c.v1"

# 需求文档第 8 章：B 侧标准化结果文件（逻辑名 → 本仓库常见实际文件名）
STANDARD_RESULT_FILES: dict[str, tuple[str, ...]] = {
    "statistics.csv": (
        "statistics.csv",
        "volcano_results.csv",
        "vip_scores.csv",
        "differential_metabolites.csv",
    ),
    "embeddings.csv": ("embeddings.csv", "pca_scores.csv", "plsda_scores.csv"),
    "prediction_results.csv": ("prediction_results.csv", "vip_scores.csv"),
    "annotation_table.csv": (
        "annotation_table.csv",
        "annotated_features.csv",
        "library_matches.csv",
        "enhanced_nodes.csv",
        "sirius_annotation_result.csv",
        "all_camera_annotated.csv",
        "csu_ms2_annotation_result.csv",
    ),
    "feature_table.csv": (
        "feature_table.csv",
        "feature_table_filtered.csv",
        "feature_table_filtered_imputed.csv",
    ),
    "enrichment_results.csv": (
        "enrichment_results.csv",
        "kegg_compound_enrich.csv",
    ),
    "result_summary.md": ("result_summary.md",),
    # 都匀毛尖论文 B 侧产出
    "tea_constituents.csv": ("tea_constituents.csv",),
    "bioactivity_assays.csv": ("bioactivity_assays.csv",),
    "sensory_scores.csv": ("sensory_scores.csv",),
    "correlation_matrix.csv": ("correlation_matrix.csv",),
    "hca_matrix.csv": ("hca_matrix.csv",),
    "differential_metabolites_abundance.csv": ("differential_metabolites_abundance.csv",),
    "volatile_differential_abundance.csv": ("volatile_differential_abundance.csv",),
    "plsda_permutation.csv": ("plsda_permutation.csv",),
    "volatile_pca_scores.csv": ("volatile_pca_scores.csv",),
    "volatile_plsda_scores.csv": ("volatile_plsda_scores.csv",),
}

PLAN_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "objective": ("objective", "分析目标", "研究目标", "scientific objective"),
    "data_understanding": ("data understanding", "数据理解", "data"),
    "workflow": ("workflow", "工作流", "pipeline"),
    "tools_required": ("tools required", "工具调配", "tools", "工具"),
    "expected_results": ("expected results", "预期结果", "expected output"),
    "required_visualization": (
        "required visualization",
        "可视化方案",
        "图表输出",
        "expected figures",
        "figures",
        "visualization",
    ),
    "interpretation_guideline": (
        "interpretation guideline",
        "结果解读",
        "interpretation",
        "解读指南",
    ),
    "reporting_plan": ("reporting plan", "报告撰写", "reporting", "报告撰写方案"),
    "assumptions": ("assumptions", "假设"),
    "risks": ("risks", "风险"),
    "references": ("references", "参考文献"),
}

DEFAULT_REPORT_SECTIONS = (
    "Introduction",
    "Methods",
    "Analysis Workflow",
    "Results",
    "Figures",
    "Scientific Interpretation",
    "Conclusion",
    "Appendix",
)


def empty_plan() -> dict:
    return {
        "contract_version": CONTRACT_VERSION,
        "plan_format": "",
        "objective": "",
        "data_understanding": "",
        "workflow": [],
        "tools_required": "",
        "expected_results": "",
        "required_visualization": [],
        "interpretations": [],
        "interpretation_guideline": "",
        "reporting_plan": {
            "language": "zh",
            "sections": list(DEFAULT_REPORT_SECTIONS),
            "audience": "",
            "decision_to_report": "",
            "references": [],
            "notes": "",
        },
        "risks": [],
        "assumptions": [],
        "references": [],
        "source": {"format": "", "path": ""},
        "warnings": [],
    }


def empty_figure_spec(
    *,
    figure_id: str = "",
    title: str = "",
    plot_type: str = "",
) -> dict:
    return {
        "figure_id": figure_id,
        "title": title,
        "plot_type": plot_type,
        "stem": "",
        "theme": "",
        "logic": "",
        "purpose": "",
        "expected_observation": "",
        "source_step": 0,
        "source_files": [],
        "description": "",
        "panels": [],
        "plot_config_hint": {},
        "raw": "",
    }


def contract_document() -> dict:
    """供 GET /api/agent-c/contract 与 A/B 对齐字段。"""
    return {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "roles": {
            "A": "分析规划：MassOmics PlanDocument 或 Web FR-2 analysis_plan.*",
            "B": "独立执行器：消费 plan_*.json，向 outputspace 写结果（默认 MassOmics-Agent-B）",
            "C": "按方案出图、写图注、汇总报告，不新增计划外分析结论",
        },
        "inputs": {
            "plan": {
                "accept": [
                    "MassOmics PlanDocument JSON（goal/steps/visualizations/interpretations/report）",
                    "plan_<timestamp>.json / .md（MassOmics manifest 产出）",
                    "analysis_plan.md（需求文档第 8.1 节 / Web FR-2）",
                    "analysis_plan.json（canonical 对象或旧版阶段列表）",
                    "Python dict",
                ],
                "formats": {
                    "massomics": {
                        "detect": "goal + steps[] 或 visualizations[]",
                        "map": "plan_adapter.normalize_massomics_plan",
                    },
                    "fr2": {
                        "detect": "objective + required_visualization[]",
                        "map": "native",
                    },
                    "legacy": {
                        "detect": "plan[] 阶段列表",
                        "map": "从 task/expected_output 推断图型",
                    },
                },
                "required_fields": [
                    "objective（或 MassOmics goal）",
                    "required_visualization（或 visualizations）",
                    "interpretation_guideline（或 interpretations[]）",
                    "reporting_plan（或 report{}）",
                ],
                "figure_fields": [
                    "figure_id",
                    "title",
                    "plot_type（由 chart_type 映射）",
                    "theme",
                    "logic",
                    "purpose",
                    "expected_observation",
                    "source_step",
                    "source_files",
                    "panels",
                    "plot_config_hint",
                ],
            },
            "results": {
                "accept": ["analysis_results/ 目录", "本仓库 mixOmics/网络等结果目录"],
                "optional_manifest": "results_manifest.json",
            },
            "options": {
                "output_dir": "C 的产出目录，默认 results_dir/agent_c_output",
                "metadata_csv": "PCA/PLS-DA 着色用；可空则在 results/upload 中查找",
                "figure_mode": "plan | available | plan_then_available",
                "language": "zh | en",
                "use_llm": "true 时写入「结果解读与科研意义」章节（LLM）；写报告会话默认开启；论文复现 repro_recipe_id 下自动关闭",
            },
        },
        "outputs": {
            "figures/": "按计划编号的 PNG/SVG 与 plot_config sidecar",
            "final_report.md": "报告正文",
            "final_report.pdf": "由 md 转换的 PDF（FR-5.5）；失败时 manifest.report.pdf 为空",
            "report_insights.json": "use_llm=true 时的 LLM 解读 JSON",
            "agent_c_manifest.json": "本轮 C 的机器可读清单",
            "captions.json": "图注与数据事实",
        },
        "python": "from web_frontend.backend.agent_c import run_agent_c, parse_plan, inventory_results",
        "cli": "python -m web_frontend.backend.agent_c --session <id> --plan plan_*.md [--dry-run]",
        "http": [
            "GET /api/agent-c/contract",
            "POST /api/agent-c/parse-plan",
            "POST /api/agent-c/inventory",
            "POST /api/agent-c/run",
            "POST /api/sessions/{session_id}/agent-c/run",
        ],
    }
