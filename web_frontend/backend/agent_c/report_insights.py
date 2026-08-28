"""Agent C 报告深度解读：基于方案 + B 结果 + 出图事实，LLM 生成意义/价值分析。

写报告（``use_llm=True``）且非论文复现（``repro_recipe_id`` 为空）时启用。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from web_frontend.backend.json_parse import extract_first_json_object

INSIGHTS_SYSTEM = """你是代谢组学/质谱数据分析报告助手。你的任务是根据用户提供的**分析方案、结果文件清单、图表事实**，
撰写「结果解读与科研意义」章节。

硬性规则：
1. 只能依据给定上下文推理；不得编造未出现的 p 值、VIP、样本数、显著特征名。
2. 区分「已产出文件/图表事实」与「方案中的预期观察」；后者不得写成已证实结论。
3. 说明分析**做了什么、能回答什么问题、对科研或应用有什么价值**；语气客观、科研写作风格。
4. 若数据不足，明确写「当前结果不足以支持……」，并建议补哪些分析。
5. 用中文输出 JSON（不要 markdown 代码块），结构：
{
  "summary": "2-4 句总体概述",
  "key_findings": ["要点1", "要点2", ...],
  "figure_interpretations": [
    {
      "figure_id": "Figure 1",
      "plot_type": "pca",
      "what_it_shows": "结合数据支撑与读图观察，本图在结果层面的含义（2-3 句）",
      "link_to_objective": "与分析目标的对应关系（1 句）",
      "caveats": "解读边界或样本量等 caution（1 句）"
    }
  ],
  "analysis_role": "本分析在整体研究中的作用（1 段）",
  "scientific_value": "科学意义（1 段）",
  "application_value": "潜在应用或决策价值（1 段，若无则写暂无）",
  "limitations": ["局限1", ...],
  "next_steps": ["建议1", ...]
}
6. figure_interpretations 必须与输入中每张已完成图的 figure_id 一一对应；缺数据的图写「当前无足够数据支撑图意解读」。
"""


def collect_report_context(
    *,
    plan: dict[str, Any],
    inventory: dict[str, Any],
    figures: list[dict[str, Any]],
    goal_text: str = "",
) -> dict[str, Any]:
    """汇总供 LLM 使用的结构化上下文（不含臆造统计）。"""
    ctx: dict[str, Any] = {
        "objective": (plan.get("objective") or "").strip(),
        "goal_text": (goal_text or "").strip()[:800],
        "data_understanding": (plan.get("data_understanding") or "").strip()[:1200],
        "workflow_steps": [],
        "expected_results": (plan.get("expected_results") or "").strip()[:800],
        "interpretation_guideline": (plan.get("interpretation_guideline") or "").strip()[:600],
        "result_summary_excerpt": (inventory.get("result_summary") or "").strip()[:1500],
        "results_dir": str(inventory.get("results_dir") or ""),
        "n_files": len(inventory.get("files") or []),
        "standard_files": {
            k: v for k, v in (inventory.get("standard_files") or {}).items() if v
        },
        "plottable_types": [
            str(p.get("plot_type")) for p in (inventory.get("plottable") or []) if p.get("plot_type")
        ],
        "figures": [],
        "quantitative_hints": [],
        "existing_result_pngs": [],
    }
    for step in plan.get("workflow") or []:
        if isinstance(step, dict):
            ctx["workflow_steps"].append(
                {
                    "stage": step.get("stage") or step.get("step_id") or step.get("name"),
                    "task": step.get("task") or step.get("description") or step.get("operations"),
                    "output": step.get("output") or step.get("expected_output"),
                }
            )
        elif step:
            ctx["workflow_steps"].append({"task": str(step)[:200]})

    for fig in figures:
        ctx["figures"].append(
            {
                "figure_id": fig.get("figure_id"),
                "title": fig.get("title"),
                "plot_type": fig.get("plot_type"),
                "status": fig.get("status"),
                "purpose": fig.get("purpose") or fig.get("theme"),
                "expected_observation": fig.get("expected_observation"),
                "facts": fig.get("facts") or [],
                "missing_reason": fig.get("missing_reason"),
                "caption_excerpt": (fig.get("caption") or "")[:400],
                "data_narrative": fig.get("data_narrative") or {},
                "vision_observation": fig.get("vision_observation") or {},
            }
        )

    ctx["quantitative_hints"] = _scan_quantitative_hints(
        Path(str(inventory.get("results_dir") or ""))
    )
    try:
        from web_frontend.backend.agent_c.report_view import list_existing_result_pngs

        root = Path(str(inventory.get("results_dir") or ""))
        ctx["existing_result_pngs"] = [
            str(x.get("rel") or x.get("name"))
            for x in list_existing_result_pngs(root, exclude_under=root / "agent_c_output")
        ][:20]
    except Exception:
        pass
    return ctx


def _scan_quantitative_hints(results_dir: Path) -> list[str]:
    """从常见结果 CSV 读取可核对计数，供 LLM 引用。"""
    hints: list[str] = []
    if not results_dir.is_dir():
        return hints
    try:
        import pandas as pd
    except ImportError:
        return hints

    scans = [
        ("volcano_results.csv", lambda df: _volcano_hint(df)),
        ("vip_scores.csv", lambda df: _vip_hint(df)),
        ("pca_scores.csv", lambda df: _scores_hint(df, "PCA")),
        ("plsda_scores.csv", lambda df: _scores_hint(df, "PLS-DA")),
        ("kegg_compound_enrich.csv", lambda df: f"KEGG 富集表 {len(df)} 行"),
        ("network_nodes.csv", lambda df: _network_nodes_hint(df)),
        ("network_edges.csv", lambda df: f"网络边 {len(df)} 条"),
        ("tea_constituents.csv", lambda df: _tea_constituents_hint(df)),
        ("bioactivity_assays.csv", lambda df: f"生物活性 {len(df)} 行"),
        ("sensory_scores.csv", lambda df: f"感官评分 {len(df)} 行"),
        ("hca_matrix.csv", lambda df: f"HCA 矩阵 {len(df)}×{len(df.columns)}"),
        ("correlation_matrix.csv", lambda df: f"相关矩阵 {len(df)} 变量"),
        ("plsda_permutation.csv", lambda df: f"置换检验 {len(df)} 行"),
        ("mass2motifs.csv", lambda df: f"Mass2Motif {len(df)} 条"),
        ("enhanced_nodes.csv", lambda df: f"注释节点 {len(df)} 个"),
    ]
    for name, fn in scans:
        path = results_dir / name
        if not path.is_file():
            for sub in results_dir.iterdir():
                if sub.is_dir():
                    alt = sub / name
                    if alt.is_file():
                        path = alt
                        break
        if not path.is_file():
            continue
        try:
            df = pd.read_csv(path)
            msg = fn(df)
            if msg:
                hints.append(f"{name}: {msg}")
        except Exception:
            continue
    return hints[:12]


def _volcano_hint(df) -> str:
    n = len(df)
    parts = [f"{n} 特征"]
    if "Significant" in df.columns:
        sig = int(df["Significant"].fillna(False).astype(bool).sum())
        parts.append(f"Significant={sig}")
    if "p_value" in df.columns:
        parts.append(f"p<0.05 约 {int((df['p_value'] < 0.05).sum())} 个")
    return "；".join(parts)


def _vip_hint(df) -> str:
    n = len(df)
    if "VIP" in df.columns:
        high = int((df["VIP"].astype(float) > 1).sum())
        return f"{n} 行，VIP>1 约 {high} 个"
    return f"{n} 行"


def _scores_hint(df, label: str) -> str:
    groups = ""
    if "Group" in df.columns:
        vc = df["Group"].astype(str).value_counts()
        groups = "，分组 " + " / ".join(f"{k}×{v}" for k, v in vc.items())
    return f"{label} 得分 {len(df)} 行{groups}"


def _network_nodes_hint(df) -> str:
    msg = f"网络节点 {len(df)} 个"
    for col in ("Family", "family"):
        if col in df.columns:
            msg += f"，{df[col].nunique()} 个家族"
            break
    return msg


def _tea_constituents_hint(df) -> str:
    parts = [f"茶叶成分 {len(df)} 行"]
    if "metric" in df.columns:
        parts.append("指标 " + "/".join(df["metric"].astype(str).unique()[:4]))
    return "；".join(parts)


def _build_user_prompt(ctx: dict[str, Any], *, zh: bool = True) -> str:
    lang = "请用中文撰写。" if zh else "Write in English."
    return (
        f"{lang}\n\n"
        "【分析目标】\n"
        f"{ctx.get('objective') or ctx.get('goal_text') or '（未提供）'}\n\n"
        "【数据理解】\n"
        f"{ctx.get('data_understanding') or '（未提供）'}\n\n"
        "【工作流步骤】\n"
        + json.dumps(ctx.get("workflow_steps") or [], ensure_ascii=False, indent=2)
        + "\n\n【结果目录概况】\n"
        f"文件数 {ctx.get('n_files')}；可出图类型 {', '.join(ctx.get('plottable_types') or []) or '无'}\n"
        f"标准映射 {json.dumps(ctx.get('standard_files') or {}, ensure_ascii=False)}\n\n"
        "【定量提示（来自 CSV，可引用）】\n"
        + ("\n".join(f"- {h}" for h in ctx.get("quantitative_hints") or []) or "（无）")
        + "\n\n【B 侧已有 PNG（可解读，路径相对 results_dir）】\n"
        + ("\n".join(f"- {p}" for p in ctx.get("existing_result_pngs") or []) or "（无）")
        + "\n\n【图表与事实】\n"
        + json.dumps(ctx.get("figures") or [], ensure_ascii=False, indent=2)
        + "\n\n【B 结果摘要摘录】\n"
        f"{ctx.get('result_summary_excerpt') or '（无）'}\n\n"
        "【方案解读指南（须遵守）】\n"
        f"{ctx.get('interpretation_guideline') or '只陈述可核对事实，不过度推断。'}\n"
    )


def generate_report_insights(
    *,
    plan: dict[str, Any],
    inventory: dict[str, Any],
    figures: list[dict[str, Any]],
    goal_text: str = "",
    language: str | None = None,
    llm_client: Any | None = None,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """调用 LLM 生成解读 JSON；失败时返回 error 字段。"""
    zh = (language or "zh").lower().startswith("zh")
    ctx = collect_report_context(
        plan=plan,
        inventory=inventory,
        figures=figures,
        goal_text=goal_text,
    )
    payload: dict[str, Any] = {"source": "llm_demo", "context_snapshot": ctx}

    try:
        if llm_client is None:
            from web_frontend.backend.web_llm import WebLLMClient

            llm_client = WebLLMClient()
        raw = llm_client.think_complete(
            [
                {"role": "system", "content": INSIGHTS_SYSTEM},
                {"role": "user", "content": _build_user_prompt(ctx, zh=zh)},
            ],
            temperature=temperature,
            max_tokens=4096,
        )
    except Exception as exc:
        payload["error"] = str(exc)
        payload["markdown"] = ""
        return payload

    if not raw or not str(raw).strip():
        payload["error"] = "LLM 返回为空"
        payload["markdown"] = ""
        return payload

    parsed = extract_first_json_object(str(raw))
    if not parsed.get("summary") and not parsed.get("key_findings"):
        payload["error"] = "LLM JSON 缺少 summary/key_findings"
        payload["raw"] = str(raw)[:2000]
        payload["markdown"] = ""
        return payload

    payload.update(parsed)
    payload["markdown"] = format_insights_markdown(parsed, zh=zh)
    return payload


def format_insights_markdown(insights: dict[str, Any], *, zh: bool = True) -> str:
    """把 insights JSON 渲染为报告 Markdown 章节。"""
    title = "## 结果解读与科研意义" if zh else "## Results interpretation"
    lines = [
        title,
        "",
        "> "
        + (
            "本节由 LLM 根据方案与结果文件事实生成；正式发表前请人工核对。"
            if zh
            else "LLM-generated section; verify before publication."
        ),
        "",
    ]
    summary = str(insights.get("summary") or "").strip()
    if summary:
        lines += [summary, ""]

    def _section(h: str, key: str, *, bullets: bool = False) -> None:
        val = insights.get(key)
        if not val:
            return
        lines.append(f"### {h}")
        lines.append("")
        if bullets and isinstance(val, list):
            for item in val:
                if str(item).strip():
                    lines.append(f"- {item}")
        elif isinstance(val, list):
            lines.append("\n".join(str(x) for x in val if str(x).strip()))
        else:
            lines.append(str(val).strip())
        lines.append("")

    if zh:
        _section("主要发现", "key_findings", bullets=True)
        _section("分析作用", "analysis_role")
        _section("科学意义", "scientific_value")
        _section("应用与决策价值", "application_value")
        _section("局限", "limitations", bullets=True)
        _section("后续建议", "next_steps", bullets=True)
    else:
        _section("Key findings", "key_findings", bullets=True)
        _section("Role of this analysis", "analysis_role")
        _section("Scientific significance", "scientific_value")
        _section("Application value", "application_value")
        _section("Limitations", "limitations", bullets=True)
        _section("Next steps", "next_steps", bullets=True)

    return "\n".join(lines).rstrip() + "\n"


def figure_interpretations_index(insights: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """figure_id → 逐图解读条目。"""
    out: dict[str, dict[str, Any]] = {}
    for item in insights.get("figure_interpretations") or []:
        if not isinstance(item, dict):
            continue
        fid = str(item.get("figure_id") or "").strip()
        if fid:
            out[fid] = item
    return out


def format_figure_interpretation_block(item: dict[str, Any] | None, *, zh: bool = True) -> str:
    if not item:
        return ""
    head = "#### 图意解读\n\n" if zh else "#### Figure interpretation\n\n"
    lines = [head]
    for key, label in (
        ("what_it_shows", "本图说明" if zh else "What this figure shows"),
        ("link_to_objective", "与目标关系" if zh else "Relation to objective"),
        ("relation_to_goal", "与目标关系" if zh else "Relation to objective"),
        ("caveats", "解读边界" if zh else "Caveats"),
    ):
        val = str(item.get(key) or "").strip()
        if val and not any(val in ln for ln in lines[1:]):
            lines.append(f"- **{label}**：{val}")
    return "\n".join(lines) + "\n" if len(lines) > 1 else ""


def merge_insights_into_report(base_markdown: str, insights_md: str, *, zh: bool = True) -> str:
    """在「科学解读」章节前插入 AI 解读块。"""
    if not insights_md.strip():
        return base_markdown
    anchor = "## 科学解读" if zh else "## Scientific Interpretation"
    if anchor in base_markdown:
        return base_markdown.replace(anchor, insights_md.rstrip() + "\n\n" + anchor, 1)
    anchor2 = "## 结论" if zh else "## Conclusion"
    if anchor2 in base_markdown:
        return base_markdown.replace(anchor2, insights_md.rstrip() + "\n\n" + anchor2, 1)
    return base_markdown.rstrip() + "\n\n" + insights_md


def should_enable_insights(*, use_llm: bool, repro_recipe_id: str | None) -> bool:
    """论文复现路径不启用 LLM 深度解读。"""
    return bool(use_llm) and not (repro_recipe_id or "").strip()


__all__ = [
    "collect_report_context",
    "figure_interpretations_index",
    "format_figure_interpretation_block",
    "generate_report_insights",
    "format_insights_markdown",
    "merge_insights_into_report",
    "should_enable_insights",
]
