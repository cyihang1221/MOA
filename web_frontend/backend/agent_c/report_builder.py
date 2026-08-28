"""按方案与出图结果组装 final_report.md，默认不调用 LLM。"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _lang(plan: dict[str, Any], override: str | None) -> str:
    if override:
        return override
    rp = plan.get("reporting_plan") or {}
    return str(rp.get("language") or "zh")


def _report_image_rel(png: str | Path, *, results_root: Path | None) -> str:
    path = Path(png).resolve()
    if results_root:
        try:
            return str(path.relative_to(results_root.resolve())).replace("\\", "/")
        except ValueError:
            pass
    parts = path.parts
    if "figures" in parts:
        idx = parts.index("figures")
        return "figures/" + "/".join(parts[idx + 1 :])
    return path.name


def _format_file_size(n: int | float | None) -> str:
    """人类可读文件大小（1024 进制）。"""
    size = int(n or 0)
    if size < 1024:
        return f"{size} B"
    if size < 1024**2:
        return f"{size / 1024:.1f} KB"
    if size < 1024**3:
        return f"{size / 1024**2:.1f} MB"
    return f"{size / 1024**3:.2f} GB"


def _clean_objective(text: str) -> str:
    """去掉附件列表、交接话术等不应出现在报告引言的内容。"""
    lines_out: list[str] = []
    in_attachment = False
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("[已上传附件]"):
            in_attachment = True
            continue
        if in_attachment:
            if stripped.startswith("- ") and (".raw" in stripped or "路径:" in stripped):
                continue
            if not stripped:
                in_attachment = False
                continue
            if stripped.startswith("路径:"):
                continue
            in_attachment = False
        if "请补充你要对结果做什么" in line or "质谱计算请交给 Agent B" in line:
            continue
        lines_out.append(line)
    return "\n".join(lines_out).strip()


def _plot_order_key(rel: str) -> tuple[int, str]:
    stem = Path(rel).stem.lower()
    for idx, key in enumerate(("pca", "plsda", "volcano", "vip", "heatmap")):
        if key in stem:
            return (idx, rel)
    return (99, rel)


def _supplement_figure_caption(item: dict[str, Any], *, zh: bool) -> str:
    rel = str(item.get("rel") or "")
    title = str(item.get("title") or Path(rel).stem.replace("_", " "))
    if zh:
        return f"**{title}**（分析工具输出，路径 `{rel}`）"
    return f"**{title}** (analysis output, `{rel}`)"


_COMPLETE_STATUSES = frozenset({"rendered", "copied_existing"})


def _figure_has_displayable_png(fig: dict[str, Any]) -> bool:
    if fig.get("status") not in _COMPLETE_STATUSES:
        return False
    png = fig.get("png")
    return bool(png and Path(str(png)).is_file())


def _sync_caption_figure_id(caption: str, old_id: str, new_id: str) -> str:
    if not caption or not old_id or old_id == new_id:
        return caption
    updated = caption.replace(f"**{old_id}.**", f"**{new_id}.**", 1)
    if updated != caption:
        return updated
    return caption.replace(f"**{old_id}**", f"**{new_id}**", 1)


def prepare_report_figures(
    figures: list[dict[str, Any]],
    *,
    supplement_existing: list[dict[str, Any]] | None = None,
    results_dir: str | Path | None = None,
    language: str | None = None,
    supplement_mode: str = "none",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """拆分可展示图与未完成图，并对成功图重编号 Figure 1…N。

    ``supplement_mode``:
    - ``none``（默认）：仅保留方案图，不并入 B 侧额外 PNG
    - ``all``：在方案图之后追加未重复的 B 侧 PNG（旧行为）
    """
    working = [dict(f) for f in figures]
    if results_dir:
        from web_frontend.backend.agent_c.report_view import apply_preferred_png_to_figures

        apply_preferred_png_to_figures(working, results_dir)

    if supplement_mode == "all" and supplement_existing and results_dir:
        working = merge_supplement_figures(
            working,
            supplement_existing,
            results_dir=results_dir,
            language=language,
        )

    complete: list[dict[str, Any]] = []
    incomplete: list[dict[str, Any]] = []
    for fig in working:
        if _figure_has_displayable_png(fig):
            complete.append(fig)
        else:
            inc = dict(fig)
            inc.setdefault("plan_figure_id", inc.get("figure_id"))
            incomplete.append(inc)

    for index, fig in enumerate(complete, start=1):
        old_id = str(fig.get("figure_id") or "")
        fig.setdefault("plan_figure_id", old_id)
        new_id = f"Figure {index}"
        fig["figure_id"] = new_id
        fig["report_figure_num"] = index
        cap = str(fig.get("caption") or "")
        if cap:
            fig["caption"] = _sync_caption_figure_id(cap, old_id, new_id)

    return complete, incomplete


def merge_supplement_figures(
    figures: list[dict[str, Any]],
    existing_figures: list[dict[str, Any]],
    *,
    results_dir: str | Path,
    language: str | None = None,
) -> list[dict[str, Any]]:
    """将 B 侧 PNG 并入统一 Figure 编号，避免报告拆成两套图表章节。"""
    zh = (language or "zh").lower().startswith("zh")
    merged = [dict(f) for f in figures]
    used_ids = {str(f.get("figure_id") or "") for f in merged if f.get("figure_id")}
    next_num = len(merged) + 1
    root = Path(results_dir)
    for item in sorted(existing_figures, key=lambda x: _plot_order_key(str(x.get("rel") or ""))):
        rel = str(item.get("rel") or "")
        if not rel:
            continue
        png = root / rel
        if not png.is_file():
            continue
        while f"Figure {next_num}" in used_ids:
            next_num += 1
        fig_id = f"Figure {next_num}"
        used_ids.add(fig_id)
        merged.append(
            {
                "figure_id": fig_id,
                "title": item.get("title") or Path(rel).stem.replace("_", " "),
                "plot_type": "",
                "png": str(png.resolve()),
                "status": "copied_existing",
                "source": "analysis_result",
                "caption": _supplement_figure_caption(item, zh=zh),
            }
        )
        next_num += 1
    return merged


def _figure_first_enabled(plan: dict[str, Any], override: bool | None) -> bool:
    if override is not None:
        return bool(override)
    rp = plan.get("reporting_plan") or {}
    if "figure_first" in rp:
        return bool(rp.get("figure_first"))
    return True


def _figure_style_provenance(figures: list[dict[str, Any]], zh: bool) -> list[str]:
    """说明本轮出图的样式来源（文献 Skill / 发表级基线）。"""
    matched: list[str] = []
    journals: list[str] = []
    warnings: list[str] = []
    for fig in figures:
        style = fig.get("literature_style")
        if not isinstance(style, dict):
            continue
        for skill in style.get("matched") or []:
            if str(skill) not in matched:
                matched.append(str(skill))
        journal = str(style.get("journal") or "")
        if journal and journal not in journals:
            journals.append(journal)
        for w in style.get("warnings") or []:
            if str(w) not in warnings:
                warnings.append(str(w))
    if not matched and not journals:
        return []

    head = "**作图规范**：" if zh else "**Figure style**: "
    if matched:
        cite = "、".join(f"`{m}`" for m in matched[:4])
        body = (
            f"首次出图即按文献 Skill {cite} 的出图清单套用样式；配色 {'/'.join(journals) or 'npg'}。"
            if zh
            else f"Initial figures follow literature skills {cite}; palette {'/'.join(journals) or 'npg'}."
        )
    else:
        body = (
            f"未匹配到针对性文献，采用发表级基线样式（配色 {'/'.join(journals) or 'npg'}）。"
            if zh
            else f"No matching literature; publication baseline style applied (palette {'/'.join(journals) or 'npg'})."
        )
    out = [head + body, ""]
    for w in warnings[:3]:
        out.append(f"> {w}")
    if warnings[:3]:
        out.append("")
    return out


def build_report_markdown(
    *,
    plan: dict[str, Any],
    inventory: dict[str, Any],
    figures: list[dict[str, Any]],
    language: str | None = None,
    existing_figures: list[dict[str, Any]] | None = None,
    results_dir: str | Path | None = None,
    figure_interpretations: dict[str, dict[str, Any]] | None = None,
    figure_first: bool | None = None,
    incomplete_figures: list[dict[str, Any]] | None = None,
    insights_enabled: bool = False,
) -> str:
    from web_frontend.backend.agent_c.figure_ecb import format_ecb_markdown_sections

    zh = _lang(plan, language).lower().startswith("zh")
    ff = _figure_first_enabled(plan, figure_first)
    results_root = Path(results_dir).resolve() if results_dir else None
    objective = _clean_objective((plan.get("objective") or "").strip()) or (
        "（方案未写分析目标）" if zh else "(objective not provided)"
    )
    title = "分析报告" if zh else "Analysis Report"
    rp = plan.get("reporting_plan") or {}

    intro_lines = [
        f"# {title}",
        "",
        f"## {'Introduction' if not zh else '引言'}",
        "",
        objective,
        "",
    ]

    methods_lines = [
        f"## {'Methods' if not zh else '方法'}",
        "",
        (plan.get("tools_required") or "").strip()
        or ("见方案工作流；本报告不补充未在方案中出现的工具参数。" if zh else "See the planned workflow. No extra tool parameters are invented here."),
        "",
    ]

    workflow_lines = [f"## {'Analysis Workflow' if not zh else '分析流程'}", ""]
    workflow = plan.get("workflow") or []
    if workflow:
        for step in workflow:
            if isinstance(step, dict):
                label = step.get("stage") or step.get("step_id") or ""
                task = step.get("task") or step.get("operations") or step.get("objective") or ""
                inp = step.get("input") or ""
                out = step.get("output") or step.get("expected_output") or ""
                tools = step.get("tools") or ""
                workflow_lines.append(f"- **{label}** {task}".strip())
                if inp:
                    workflow_lines.append(f"  - {'输入' if zh else 'Input'}: {inp}")
                if tools:
                    workflow_lines.append(f"  - {'工具' if zh else 'Tools'}: {tools}")
                if out:
                    workflow_lines.append(f"  - {'预期输出' if zh else 'Expected output'}: {out}")
            else:
                workflow_lines.append(f"- {step}")
    else:
        workflow_lines.append(plan.get("data_understanding") or ("（方案未列出逐步工作流）" if zh else "(no workflow section)"))

    expected = (plan.get("expected_results") or "").strip()
    if expected:
        workflow_lines += ["", f"### {'预期结果（方案）' if zh else 'Expected results (plan)'}", "", expected, ""]

    results_lines = ["", f"## {'Results' if not zh else '结果'}", ""]
    summary = (inventory.get("result_summary") or "").strip()
    if summary:
        results_lines.append(summary)
        results_lines.append("")
    else:
        n_files = len(inventory.get("files") or [])
        n_plot = len(inventory.get("plottable") or [])
        results_lines.append(
            f"{'结果目录文件' if zh else 'Result files'}: {n_files}；"
            f"{'可渲染图类型' if zh else 'plottable types'}: {n_plot}。"
        )
        std = inventory.get("standard_files") or {}
        present = [f"{k}→{v}" for k, v in std.items() if v]
        if present:
            results_lines.append(("标准化结果映射：" if zh else "Standard file mapping: ") + "; ".join(present))
        results_lines.append("")

    figures_lines = [f"## {'Figures' if not zh else '图表'}", ""]
    figures_lines += _figure_style_provenance(figures, zh)
    if not figures:
        figures_lines.append("（无图表）" if zh else "(no figures)")
    for fig in figures:
        fig_id = fig.get("figure_id") or ""
        png = fig.get("png")
        status = fig.get("status")
        figures_lines.append(f"### {fig_id}")
        figures_lines.append("")
        if status in {"rendered", "copied_existing"} and png:
            rel = _report_image_rel(png, results_root=results_root)
            figures_lines.append(f"![{fig_id}]({rel})")
            figures_lines.append("")
        figures_lines.append(fig.get("caption") or "")
        figures_lines.append("")
        fid = str(fig.get("figure_id") or "")
        interp = (figure_interpretations or {}).get(fid) if figure_interpretations else None
        figures_lines.append(
            format_ecb_markdown_sections(
                fig,
                interp,
                insights_enabled=insights_enabled,
                zh=zh,
            )
        )
        if fig.get("missing_reason") and status not in _COMPLETE_STATUSES:
            figures_lines.append("")
            figures_lines.append(f"> {'未完成原因' if zh else 'Incomplete'}: {fig['missing_reason']}")
        figures_lines.append("")

    if ff:
        lines = intro_lines + figures_lines + methods_lines + workflow_lines + results_lines
    else:
        lines = intro_lines + methods_lines + workflow_lines + results_lines + figures_lines

    lines += [f"## {'Scientific Interpretation' if not zh else '科学解读'}", ""]
    guide = (plan.get("interpretation_guideline") or "").strip()
    if guide:
        lines.append(guide)
        lines.append("")
    interps = plan.get("interpretations") or []
    if interps:
        lines.append("### " + ("方案解读要点" if zh else "Planned interpretation items"))
        lines.append("")
        for it in interps:
            if isinstance(it, dict):
                target = str(it.get("target") or "").strip()
                criteria = str(it.get("criteria") or "").strip()
                note = str(it.get("note") or "").strip()
                body = "；".join(p for p in (criteria, note) if p)
                if target and body:
                    lines.append(f"- **{target}**：{body}")
                elif body:
                    lines.append(f"- {body}")
            else:
                lines.append(f"- {it}")
        lines.append("")
    decision = str(rp.get("decision_to_report") or "").strip()
    if decision:
        lines.append(("**结论导出（方案）**：" if zh else "**Decision to report (plan)**: ") + decision)
        lines.append("")
    lines.append(
        "以下区分方案中的**预期观察**与结果文件中的**可核对事实**。未在结果文件出现的数值一律不写。"
        if zh
        else "Planned observations are not treated as confirmed findings. Numbers appear only if present in result files."
    )
    lines.append("")
    for fig in figures:
        facts = fig.get("facts") or []
        expected = fig.get("expected_observation") or ""
        lines.append(f"- **{fig.get('figure_id')}**")
        if expected:
            lines.append(f"  - {'方案预期（非结论）' if zh else 'Planned (not a result)'}: {expected}")
        if facts:
            lines.append(f"  - {'文件事实' if zh else 'File facts'}: " + "；".join(facts))
        elif fig.get("missing_reason"):
            lines.append(f"  - {fig['missing_reason']}")
        else:
            lines.append(f"  - {'无额外计数' if zh else 'No extra counts'}")
    lines.append("")

    lines += [f"## {'Conclusion' if not zh else '结论'}", ""]
    rendered_ok = [f for f in figures if _figure_has_displayable_png(f)]
    missing = list(incomplete_figures or [])
    if zh:
        lines.append(
            f"本轮按方案完成 {len(rendered_ok)} 张图"
            + (f"，{len(missing)} 张因数据或渲染缺失未完成" if missing else "。")
        )
        lines.append("结论仅覆盖已生成图表与文件计数；机制性推断需用户或后续迭代补充，且必须引用对应图号。")
    else:
        lines.append(
            f"{len(rendered_ok)} figure(s) completed"
            + (f"; {len(missing)} incomplete." if missing else ".")
        )
        lines.append("No mechanistic claims are added beyond file facts and the planned interpretation guideline.")
    lines.append("")

    lines += [f"## {'Appendix' if not zh else '附录'}", ""]
    if missing:
        lines += [
            "### " + ("未完成图表（方案）" if zh else "Incomplete figures (plan)"),
            "",
        ]
        for fig in missing:
            plan_id = fig.get("plan_figure_id") or fig.get("figure_id") or ""
            plot_type = str(fig.get("plot_type") or "").strip()
            label = f"**{plan_id}**"
            if plot_type:
                label += f" (`{plot_type}`)"
            lines.append(f"- {label}")
            reason = str(fig.get("missing_reason") or "").strip()
            if reason:
                lines.append(f"  - {reason}")
        lines.append("")
    lines.append(("结果目录：" if zh else "Results directory: ") + str(inventory.get("results_dir") or ""))
    lines.append("")
    lines.append("| file | size |")
    lines.append("|------|------|")
    for info in (inventory.get("files") or [])[:80]:
        size = _format_file_size(info.get("size"))
        lines.append(f"| `{info.get('rel')}` | {size} |")
    notes = ((plan.get("reporting_plan") or {}).get("notes") or "").strip()
    audience = str(rp.get("audience") or "").strip()
    if audience:
        lines += ["", ("目标读者：" if zh else "Audience: ") + audience]
    if notes:
        lines += ["", ("方案中的报告撰写说明：" if zh else "Reporting notes from the plan:"), "", notes]

    assumptions = plan.get("assumptions") or []
    risks = plan.get("risks") or []
    references = plan.get("references") or []
    if assumptions:
        lines += ["", "### " + ("假设" if zh else "Assumptions")]
        lines += [f"- {a}" for a in assumptions]
    if risks:
        lines += ["", "### " + ("风险" if zh else "Risks")]
        lines += [f"- {r}" for r in risks]
    if references:
        lines += ["", "### " + ("参考文献" if zh else "References")]
        lines += [f"- {r}" for r in references]
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(markdown: str, output_dir: Path) -> Path:
    path = Path(output_dir) / "final_report.md"
    path.write_text(markdown, encoding="utf-8")
    return path
