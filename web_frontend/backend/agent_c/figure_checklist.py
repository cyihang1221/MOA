"""Agent C Phase 1：对照方案 Figure 蓝图输出缺数据 checklist。"""
from __future__ import annotations

from typing import Any


def checklist_from_jobs(
    jobs: list[dict[str, Any]],
    *,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """从 match_figures 的 jobs 汇总就绪/缺失状态。"""
    ready: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for job in jobs:
        entry = {
            "figure_id": job.get("figure_id"),
            "plot_type": job.get("plot_type"),
            "source_step": job.get("source_step") or 0,
            "source_files": list(job.get("source_files") or []),
            "status": job.get("status"),
            "missing_reason": job.get("missing_reason") or "",
        }
        if job.get("status") == "ready":
            ready.append(entry)
        else:
            missing.append(entry)
    repro = (plan or {}).get("reproduction_target") or {}
    return {
        "n_total": len(jobs),
        "n_ready": len(ready),
        "n_missing": len(missing),
        "ready": ready,
        "missing": missing,
        "reproduction_target": repro,
        "completion_rate": round(len(ready) / len(jobs), 3) if jobs else 0.0,
    }


def format_checklist_markdown(
    checklist: dict[str, Any],
    *,
    language: str = "zh",
) -> str:
    """生成用户可读的补齐指引（SSE / 报告）。"""
    zh = (language or "zh").lower().startswith("zh")
    lines: list[str] = []
    repro = checklist.get("reproduction_target") or {}
    if repro.get("short_title") or repro.get("recipe_id"):
        title = repro.get("short_title") or repro.get("recipe_id")
        lines.append(
            f"📋 **论文复现 Figure checklist** — {title}"
            + (f"（DOI `{repro.get('doi')}`）" if repro.get("doi") else "")
        )
    else:
        lines.append("📋 **Figure 数据 checklist**（对照 Agent A 蓝图）")
    n_ready = checklist.get("n_ready") or 0
    n_total = checklist.get("n_total") or 0
    lines.append(f"- 就绪：**{n_ready}/{n_total}** 张可出图")
    lines.append("")

    missing = checklist.get("missing") or []
    if not missing:
        lines.append("✅ 方案中的图均已有对应数据文件，可继续渲染。" if zh else "✅ All planned figures have data.")
        return "\n".join(lines)

    lines.append("⚠️ **仍缺数据（需 Agent B 先写入 outputspace）**：" if zh else "⚠️ **Missing data (Agent B must write files first):**")
    for item in missing[:12]:
        fid = item.get("figure_id") or "Figure"
        pt = item.get("plot_type") or "?"
        step = item.get("source_step") or "?"
        sfiles = ", ".join(item.get("source_files") or []) or "（见 PlotSpec）"
        reason = item.get("missing_reason") or ""
        lines.append(f"- **{fid}** `{pt}`：Step {step} → 需要 `{sfiles}`")
        if reason:
            lines.append(f"  - {reason}")
    if len(missing) > 12:
        lines.append(f"- … 另有 {len(missing) - 12} 项")

    lines.append("")
    if zh:
        lines.append(
            "**建议操作**：\n"
            "1. 若尚未执行分析 → 回复 **确认计划** 启动 Agent B；\n"
            "2. 若 B 已跑但缺文件 → 检查对应 Step 日志，或说明要 **重跑** 哪一步；\n"
            "3. 仅缺个别图 → 确认 `statistical_results/` 等目录是否含上述 CSV。"
        )
    return "\n".join(lines)


def merge_repro_and_plan_checklist(
    plan_checklist: dict[str, Any],
    repro_checklist: dict[str, Any] | None,
) -> dict[str, Any]:
    """合并 plan jobs checklist 与 repro recipe 文件级 checklist。"""
    if not repro_checklist:
        return plan_checklist
    merged = dict(plan_checklist)
    merged["repro_file_checklist"] = repro_checklist
    merged["n_repro_ready_figures"] = repro_checklist.get("n_ready_figures")
    merged["n_repro_total_figures"] = repro_checklist.get("n_total_figures")
    merged["repro_missing_files"] = repro_checklist.get("missing") or []
    return merged


__all__ = [
    "checklist_from_jobs",
    "format_checklist_markdown",
    "merge_repro_and_plan_checklist",
]
