"""MassAgent 网页编排：A / B / C 三个独立智能体的交接契约。

三个角色分开工作，网页只做编排（上传 → 计划评审 → 执行 → 出图/报告）。
不要调用 MassOmics ``Agent.run()``（那会在同一进程里重做规划并写报告）。
"""
from __future__ import annotations

CONTRACT_VERSION = "1.2"
CONTRACT_ID = "massagent.abc.v1"


def contract_document() -> dict:
    return {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "principle": (
            "A、B、C 是三个独立智能体；网页编排器只传递文件路径，"
            "不把三者合成一个 Agent，也不让 B 再规划、不让 C 跑分析工具。"
        ),
        "flow": [
            "用户上传数据 + 分析目标",
            "Agent A 写出 PlanDocument（plan_*.json）与 analysis_plan.md，停在待确认",
            "用户确认计划（需求 AC-2）",
            "Agent B 读取 plan_*.json，在独立进程中执行 MassOmics 工具，写入 outputspace",
            "Agent C 读取方案 + results_dir，出图并写报告",
        ],
        "agents": {
            "A": {
                "role": "分析规划",
                "module": "web_frontend.backend.agent_a",
                "backend_env": "WEB_AGENT_A_BACKEND=massomics|local（默认 massomics）",
                "code_root_env": "WEB_MASSOMICS_ROOT（未设则探测：本仓 plan/ 或 MassOmics-Agent/MassOmics-Agent）",
                "input": ["会话 inputspace 数据", "用户分析目标"],
                "output": [
                    "outputspace/<slug>/plan_<timestamp>.json（MassOmics PlanDocument）",
                    "outputspace/<slug>/plan_<timestamp>.md",
                    "outputspace/<slug>/analysis_plan.md / analysis_plan.json（评审与 C 用）",
                ],
                "must_not": ["调用分析 MCP", "写出最终报告"],
                "python": "from web_frontend.backend.agent_a import run_massomics_planning",
                "cli": "python -m web_frontend.backend.agent_a --session <slug>",
            },
            "B": {
                "role": "分析执行",
                "module": "web_frontend.backend.agent_b",
                "backend_env": "WEB_AGENT_B_BACKEND=massomics|local（默认 massomics）",
                "code_root_env": "WEB_MASSOMICS_B_ROOT（未设则探测：MassOmics-Agent-B 或本仓 src/executor）",
                "input": [
                    "A 的 plan_*.json",
                    "会话 inputspace（--data）",
                    "可选 metadata.csv",
                ],
                "output": [
                    "outputspace/<对话名称>/<工具名称>/结果/（catalog 名如 CAMERA、mixOmics）",
                    "outputspace/<对话名称>/agent_b_receipt.json",
                    "outputspace/<对话名称>/agent_b_adapted_plan.json",
                ],
                "must_not": [
                    "重新规划（不调用 plan_phase / Agent.run）",
                    "写 Agent C 报告",
                ],
                "python": "from web_frontend.backend.agent_b import stream_massomics_b_execution",
                "cli": "python -m web_frontend.backend.agent_b --session <slug>",
            },
            "C": {
                "role": "可视化与报告",
                "module": "web_frontend.backend.agent_c",
                "input": ["A 的方案（plan 或 analysis_plan）", "B 的 results_dir"],
                "output": ["outputspace/<slug>/agent_c_output/"],
                "must_not": ["改 A 的计划", "重跑 B 的计算工具"],
                "python": "from web_frontend.backend.agent_c import run_agent_c",
                "cli": "python -m web_frontend.backend.agent_c --session <slug>",
                "http": "GET /api/agent-c/contract",
            },
        },
        "handoffs": [
            {
                "from": "A",
                "to": "B",
                "artifact": "plan_*.json（goal + steps[]）",
                "note": (
                    "B 按 origin/B 的 tool_catalog 补全 stage/keyword，再 adapt_massomics_plan。"
                    "跨步默认吃上一阶段产物，不信任 A 猜的绝对路径。"
                    "统计分析前若无 kNN 会自动插入。"
                ),
            },
            {
                "from": "A",
                "to": "C",
                "artifact": "plan_*.json 或 analysis_plan.md / analysis_plan.json",
            },
            {
                "from": "B",
                "to": "C",
                "artifact": "results_dir = outputspace/<对话名称>/；工具结果在 <工具名称>/结果/",
            },
        ],
        "canonical_files": {
            "b_output_layout": "outputspace/<对话名称>/<工具名称>/结果/",
            "feature_table_directory": [
                "feature_table.csv（含 feature_id, mz, rt/rt_med, 样本强度）",
                "不要把 feature_values_into.csv（无 mz）或 feature_definitions.csv 当峰表",
            ],
            "imputed_feature_table_directory": [
                "feature_table_filtered_imputed.csv",
                "也接受 feature_table_filtered.csv / feature_table.csv",
            ],
            "spectra_directory": [
                "differential_spectra.mgf + differential_feature_table.csv（差异提取后）",
                "若无差异谱，回退 XCMS 的 spectra.mgf + feature_table.csv",
                "全量谱超过 ABC_MAX_ID_SPECTRA（默认 50）时截断，避免 SIRIUS 跑数小时",
            ],
            "supervised_stats": [
                "metadata.csv 需要 Sample, Group；每组 n>=2 才跑 PLS-DA/VIP",
                "n=1 时只保留 PCA，并写 mixomics_skip_supervised.txt",
            ],
        },
        "http": [
            "GET /api/abc/contract",
            "GET /api/agent-backends",
            "GET /api/agent-c/contract",
        ],
    }


__all__ = ["CONTRACT_ID", "CONTRACT_VERSION", "contract_document"]
