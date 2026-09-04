"""Agent C 主入口：A 的方案 + B 的结果 → 图 + 报告。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from web_frontend.backend.agent_c.contract import CONTRACT_VERSION
from web_frontend.backend.agent_c.figure_pipeline import (
    match_figures,
    render_jobs,
    write_captions_json,
)
from web_frontend.backend.agent_c.plan_parser import parse_plan
from web_frontend.backend.agent_c.pdf_export import markdown_file_to_pdf
from web_frontend.backend.agent_c.report_builder import build_report_markdown, write_report
from web_frontend.backend.agent_c.results_inventory import find_metadata_csv, inventory_results


def _plan_goal_text(parsed: dict[str, Any]) -> str:
    """从方案拼出用于文献匹配的目标上下文。"""
    parts: list[str] = []
    objective = str(parsed.get("objective") or "").strip()
    if objective:
        parts.append(objective)
    for fig in (parsed.get("required_visualization") or [])[:6]:
        if not isinstance(fig, dict):
            continue
        for key in ("title", "theme", "purpose"):
            val = str(fig.get(key) or "").strip()
            if val:
                parts.append(val)
    return "\n".join(parts)[:1200]


def _literature_summary(figures: list[dict[str, Any]], goal: str) -> dict[str, Any]:
    """汇总首次出图用到的文献样式来源，便于报告与前端追溯。"""
    matched: set[str] = set()
    journals: set[str] = set()
    warnings: list[str] = []
    n_lit = 0
    for fig in figures:
        style = fig.get("literature_style")
        if not isinstance(style, dict):
            continue
        if style.get("source") == "literature":
            n_lit += 1
        matched.update(str(m) for m in (style.get("matched") or []) if m)
        if style.get("journal"):
            journals.add(str(style["journal"]))
        for w in style.get("warnings") or []:
            if w not in warnings:
                warnings.append(str(w))
    return {
        "enabled": bool(journals),
        "goal_text": goal[:400],
        "n_figures_with_literature": n_lit,
        "matched_skills": sorted(matched),
        "palettes": sorted(journals),
        "warnings": warnings[:10],
    }


def run_agent_c(
    *,
    plan: str | Path | dict[str, Any] | None = None,
    results_dir: str | Path,
    output_dir: str | Path | None = None,
    metadata_csv: str | Path | None = None,
    figure_mode: str = "plan",
    language: str | None = None,
    use_llm: bool = False,
    goal_text: str = "",
    project_root: str | Path | None = None,
    use_literature: bool = True,
    repro_recipe_id: str | None = None,
) -> dict[str, Any]:
    """执行 C：出图并写 ``final_report.md``。

    Args:
        plan: A 的 analysis_plan.md / .json / dict
        results_dir: B 的结果目录
        output_dir: C 产出目录，默认 ``<results_dir>/agent_c_output``
        metadata_csv: 样本分组表；空则在结果目录查找
        figure_mode: ``plan`` 只出方案中的图；``available`` 出所有可渲染结果；
            ``plan_then_available`` 先方案再补齐
        language: ``zh`` / ``en``；空则用方案 reporting_plan.language
        use_llm: 为 true 时启用 **AI 深度解读**（结果意义/价值章节）；
            论文复现（``repro_recipe_id``）路径下自动关闭。
        goal_text: 分析目标上下文，用于匹配文献作图知识；空则退回方案 objective
        project_root: 文献 Skill 根目录；空则用包内推断
        use_literature: 首次出图是否套用文献样式（关闭时只用发表级基线）
        repro_recipe_id: 论文复现配方 ID（如 ``duyun_maojian_fochx_2026``）；指定时可用配方替代 plan
    """
    from web_frontend.backend.agent_c.paper_reproduction import (
        checklist_inventory,
        load_repro_recipe,
        recipe_to_canonical_plan,
    )

    repro_checklist: dict[str, Any] | None = None
    if repro_recipe_id:
        recipe = load_repro_recipe(repro_recipe_id)
        parsed = recipe_to_canonical_plan(recipe)
    elif plan is not None:
        parsed = parse_plan(plan)
    else:
        raise ValueError("必须提供 plan 或 repro_recipe_id")
    results = Path(results_dir)
    out = Path(output_dir) if output_dir else results / "agent_c_output"
    out.mkdir(parents=True, exist_ok=True)

    inv = inventory_results(results, metadata_csv=metadata_csv)
    if repro_recipe_id:
        repro_checklist = checklist_inventory(recipe, inv)
    meta = metadata_csv or inv.get("metadata_csv") or find_metadata_csv(results)

    from web_frontend.backend.literature_plot_knowledge import effective_plot_goal_text

    goal = effective_plot_goal_text(user_message=goal_text, plan=parsed)
    figure_mode_effective = figure_mode
    from web_frontend.backend.agent_c.report_insights import should_enable_insights

    insights_enabled = should_enable_insights(use_llm=use_llm, repro_recipe_id=repro_recipe_id)
    # 深度报告仍用 LLM 写解读；B 侧 ggplot 只进 existing_figures 附录。
    # 首次出图必须走 Vega-Lite 文献样式，不能因为写报告就复制 mixOmics PNG。

    jobs = match_figures(parsed, inv, figure_mode=figure_mode_effective)
    from web_frontend.backend.agent_c.figure_checklist import (
        checklist_from_jobs,
        format_checklist_markdown,
        merge_repro_and_plan_checklist,
    )

    plan_checklist = checklist_from_jobs(jobs, plan=parsed)
    figure_checklist = merge_repro_and_plan_checklist(plan_checklist, repro_checklist)
    figure_checklist_md = format_checklist_markdown(figure_checklist, language=language or "zh")

    figures = render_jobs(
        jobs,
        output_dir=out,
        metadata_csv=meta,
        language=language or "zh",
        goal_text=goal,
        project_root=Path(project_root) if project_root else None,
        use_literature=use_literature,
        use_existing_when_available=insights_enabled and not use_literature,
    )
    captions_path = write_captions_json(figures, out)
    warnings = list(parsed.get("warnings") or []) + list(inv.get("warnings") or [])

    from web_frontend.backend.agent_c.report_builder import prepare_report_figures
    from web_frontend.backend.agent_c.report_view import (
        filter_existing_figures_for_report,
        list_existing_result_pngs,
    )

    existing_figures = filter_existing_figures_for_report(
        list_existing_result_pngs(results, exclude_under=out),
        figures=figures,
        results_dir=results,
    )
    supplement_mode = "all" if figure_mode_effective in {"available", "plan_then_available"} else "none"
    report_figures, incomplete_figures = prepare_report_figures(
        figures,
        supplement_existing=existing_figures,
        results_dir=results,
        language=language,
        supplement_mode=supplement_mode,
    )

    from web_frontend.backend.agent_c.figure_data_narrative import enrich_figures_data_narrative
    from web_frontend.backend.agent_c.figure_vision import attach_vision_to_figures

    enrich_figures_data_narrative(
        report_figures,
        results_dir=results,
        metadata_csv=meta,
    )

    insights_payload: dict[str, Any] | None = None
    figure_interp: dict[str, dict[str, Any]] = {}
    from web_frontend.backend.agent_c.report_insights import (
        figure_interpretations_index,
        generate_report_insights,
        merge_insights_into_report,
    )

    zh_report = (language or "zh").lower().startswith("zh")
    if insights_enabled:
        attach_vision_to_figures(
            report_figures,
            objective=str(parsed.get("objective") or goal),
        )
        try:
            insights_payload = generate_report_insights(
                plan=parsed,
                inventory=inv,
                figures=report_figures,
                goal_text=goal,
                language=language,
            )
            figure_interp = figure_interpretations_index(insights_payload or {})
        except Exception as exc:
            warnings.append(f"深度解读失败: {exc}")

    markdown = build_report_markdown(
        plan=parsed,
        inventory=inv,
        figures=report_figures,
        language=language,
        results_dir=results,
        figure_interpretations=figure_interp,
        incomplete_figures=incomplete_figures,
        insights_enabled=insights_enabled,
    )

    from web_frontend.backend.agent_c.figure_cards import build_figure_cards, write_figure_cards_json

    figure_cards = build_figure_cards(
        report_figures,
        figure_interp,
        results_root=results,
        zh=zh_report,
        insights_enabled=insights_enabled,
    )
    figure_cards_path = write_figure_cards_json(figure_cards, out)
    if insights_enabled and insights_payload:
        try:
            if insights_payload.get("markdown"):
                markdown = merge_insights_into_report(
                    markdown,
                    str(insights_payload["markdown"]),
                    zh=zh_report,
                )
                (out / "report_insights.json").write_text(
                    json.dumps(insights_payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            elif insights_payload.get("error"):
                warnings.append(f"深度解读未生成: {insights_payload['error']}")
        except Exception as exc:
            warnings.append(f"深度解读合并失败: {exc}")

    report_path = write_report(markdown, out)
    pdf_path = None
    try:
        pdf_path = markdown_file_to_pdf(report_path, results_dir=results)
    except Exception as exc:
        warnings.append(f"PDF 未生成: {exc}")

    ok = [f for f in report_figures if f.get("status") in {"rendered", "copied_existing"}]
    failed = list(incomplete_figures)
    if not report_figures:
        status = "failed"
    elif failed and ok:
        status = "partial"
    elif failed and not ok:
        status = "failed"
    else:
        status = "ok"

    if use_llm and repro_recipe_id:
        warnings.append("论文复现模式未启用 LLM 深度解读")

    manifest = {
        "contract_version": CONTRACT_VERSION,
        "status": status,
        "plan_warnings": parsed.get("warnings") or [],
        "results_dir": str(results.resolve()) if results.exists() else str(results),
        "output_dir": str(out.resolve()),
        "metadata_csv": str(meta) if meta else None,
        "figure_mode": figure_mode,
        "figures": [
            {
                "figure_id": f.get("figure_id"),
                "plot_type": f.get("plot_type"),
                "status": f.get("status"),
                "png": f.get("png"),
                "svg": f.get("svg"),
                "caption": f.get("caption"),
                "missing_reason": f.get("missing_reason"),
                "literature_style": f.get("literature_style"),
                "style_note": f.get("style_note"),
            }
            for f in figures
        ],
        "report_figures": [
            {
                "figure_id": card.get("figure_id"),
                "plot_type": card.get("plot_type"),
                "status": card.get("status"),
                "png": f.get("png"),
                "rel": card.get("rel"),
                "source": card.get("source"),
                "caption": card.get("caption"),
                "data_narrative": f.get("data_narrative"),
                "vision_observation": f.get("vision_observation"),
                "interpretation": figure_interp.get(str(f.get("figure_id") or "")),
            }
            for f, card in zip(report_figures, figure_cards)
        ],
        "figure_cards": str(figure_cards_path),
        "report_layout": "figure_first",
        "literature_style": _literature_summary(figures, goal),
        "report": {
            "markdown": str(report_path),
            "pdf": str(pdf_path) if pdf_path else None,
            "insights_enabled": insights_enabled,
            "insights_json": str(out / "report_insights.json")
            if insights_payload and insights_payload.get("markdown")
            else None,
        },
        "captions": str(captions_path),
        "warnings": warnings,
        "n_rendered": len(ok),
        "n_incomplete": len(failed),
        "incomplete_figures": [
            {
                "plan_figure_id": f.get("plan_figure_id") or f.get("figure_id"),
                "plot_type": f.get("plot_type"),
                "status": f.get("status"),
                "missing_reason": f.get("missing_reason"),
            }
            for f in incomplete_figures
        ],
        "figure_checklist": figure_checklist,
        "figure_checklist_md": figure_checklist_md,
    }
    if repro_checklist is not None:
        manifest["reproduction_checklist"] = repro_checklist
        manifest["repro_recipe_id"] = repro_recipe_id
    manifest_path = out / "agent_c_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["manifest"] = str(manifest_path)
    parsed_path = out / "parsed_plan.json"
    parsed_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    inv_path = out / "results_inventory.json"
    inv_path.write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
