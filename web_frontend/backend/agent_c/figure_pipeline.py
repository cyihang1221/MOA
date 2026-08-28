"""按方案把 B 的结果渲染成科研图。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from web_frontend.backend.literature_figure_style import (
    build_initial_plot_config,
    style_provenance_line,
)
from web_frontend.backend.plot_edit_registry import get_plot_spec
from web_frontend.backend.semantic_plot_renderer import (
    build_vegalite_spec,
    write_semantic_outputs,
)


def _inventory_file_names(inventory: dict[str, Any]) -> dict[str, dict]:
    """文件名（小写）→ plottable 条目（用于 source_files 优先匹配）。"""
    index: dict[str, dict] = {}
    for item in inventory.get("plottable") or []:
        for fname in item.get("data_files") or []:
            index[str(fname).lower()] = item
    return index


def _pick_plottable(
    plot_type: str,
    *,
    by_type: dict[str, list[dict]],
    file_index: dict[str, dict],
    source_files: list[str],
    used: set[str],
) -> dict | None:
    """优先按 source_files 匹配，再按 plot_type 池取用。"""
    for sf in source_files:
        base = str(sf).split("/")[-1].lower()
        hit = file_index.get(base)
        if hit and str(hit.get("plot_type")) == plot_type:
            key = f"{hit['plot_type']}:{hit['data_dir']}"
            if key not in used:
                used.add(key)
                return hit
    pool = by_type.get(plot_type) or []
    for item in pool:
        key = f"{item['plot_type']}:{item['data_dir']}"
        if key in used:
            continue
        used.add(key)
        return item
    return pool[0] if pool else None


def match_figures(
    plan: dict[str, Any],
    inventory: dict[str, Any],
    *,
    figure_mode: str = "plan",
) -> list[dict[str, Any]]:
    """把计划中的图与 B 可渲染条目对齐。"""
    plottable = list(inventory.get("plottable") or [])
    by_type: dict[str, list[dict]] = {}
    for item in plottable:
        by_type.setdefault(str(item.get("plot_type")), []).append(item)
    file_index = _inventory_file_names(inventory)

    used: set[str] = set()
    jobs: list[dict[str, Any]] = []
    planned = list(plan.get("required_visualization") or [])
    mode = (figure_mode or "plan").strip().lower()
    if mode not in {"plan", "available", "plan_then_available"}:
        mode = "plan"
    if mode == "plan" and not planned:
        mode = "available"

    def _take(plot_type: str, source_files: list[str] | None = None) -> dict | None:
        return _pick_plottable(
            plot_type,
            by_type=by_type,
            file_index=file_index,
            source_files=source_files or [],
            used=used,
        )

    if mode in {"plan", "plan_then_available"}:
        for fig in planned:
            plot_type = str(fig.get("plot_type") or "")
            source_files = [str(f) for f in (fig.get("source_files") or []) if f]
            job = {
                "figure_id": fig.get("figure_id") or "",
                "title": fig.get("title") or fig.get("theme") or plot_type,
                "plot_type": plot_type,
                "stem": fig.get("stem") or "",
                "theme": fig.get("theme") or "",
                "logic": fig.get("logic") or "",
                "purpose": fig.get("purpose") or "",
                "expected_observation": fig.get("expected_observation") or "",
                "source_step": fig.get("source_step") or 0,
                "source_files": source_files,
                "panels": fig.get("panels") or [],
                "plot_config_hint": fig.get("plot_config_hint") or {},
                "source": "plan",
            }
            hit = _take(plot_type, source_files) if plot_type else None
            if hit:
                job.update(
                    {
                        "data_dir": hit["data_dir"],
                        "data_files": hit["data_files"],
                        "existing_png": hit.get("existing_png"),
                        "stem": hit.get("stem") or job["stem"],
                        "status": "ready",
                    }
                )
            else:
                job["status"] = "missing_data"
                job["missing_reason"] = (
                    f"方案需要 {plot_type or '未识别图型'}"
                    + (f"（Step {job.get('source_step')} 预期 {', '.join(source_files)}）" if source_files else "")
                    + "，但结果目录没有对应数据文件"
                    if plot_type
                    else "方案未给出可映射的 plot_type"
                )
            jobs.append(job)

    if mode in {"available", "plan_then_available"}:
        for item in plottable:
            key = f"{item['plot_type']}:{item['data_dir']}"
            if key in used:
                continue
            # B 侧已有 PNG 时不再补渲染任务（报告 existing_figures 会引用）
            if item.get("existing_png"):
                continue
            used.add(key)
            jobs.append(
                {
                    "figure_id": f"Figure {len(jobs) + 1}",
                    "title": item.get("title") or item["stem"],
                    "plot_type": item["plot_type"],
                    "stem": item["stem"],
                    "theme": "",
                    "logic": "",
                    "purpose": "方案未点名；因结果中已有数据而补出",
                    "expected_observation": "",
                    "panels": [],
                    "plot_config_hint": {},
                    "data_dir": item["data_dir"],
                    "data_files": item["data_files"],
                    "existing_png": item.get("existing_png"),
                    "status": "ready",
                    "source": "available",
                }
            )
    return jobs


def extract_figure_facts(plot_type: str, data_dir: str | Path) -> list[str]:
    """只从结果文件计数，不编造显著性结论。"""
    facts: list[str] = []
    root = Path(data_dir)
    try:
        import pandas as pd
    except ImportError:
        return facts

    spec = get_plot_spec(plot_type)
    if not spec:
        return facts
    try:
        if plot_type in {"pca", "plsda"}:
            path = root / spec.data_files[0]
            if path.is_file():
                n = len(pd.read_csv(path))
                facts.append(f"得分数 {n} 行")
        elif plot_type == "volcano":
            path = root / spec.data_files[0]
            if path.is_file():
                df = pd.read_csv(path)
                facts.append(f"火山表 {len(df)} 行")
                if "Significant" in df.columns:
                    n_sig = int(df["Significant"].fillna(False).astype(bool).sum())
                    facts.append(f"Significant=True {n_sig} 行")
        elif plot_type in {"kegg_bubble", "kegg_dotplot", "kegg_barplot"}:
            path = root / spec.data_files[0]
            if path.is_file():
                facts.append(f"富集表 {len(pd.read_csv(path))} 行")
        elif plot_type == "network_topology":
            path = root / spec.data_files[0]
            if path.is_file():
                facts.append(f"布局表 {len(pd.read_csv(path))} 个节点")
        elif plot_type == "vip_bar":
            path = root / spec.data_files[0]
            if path.is_file():
                facts.append(f"VIP 表 {len(pd.read_csv(path))} 行")
    except Exception:
        return facts
    return facts


def _build_caption(job: dict[str, Any], facts: list[str], language: str) -> str:
    fig_id = job.get("figure_id") or "Figure"
    title = job.get("title") or job.get("plot_type") or ""
    zh = (language or "zh").lower().startswith("zh")
    parts = [f"**{fig_id}.** {title}".strip()]
    if job.get("source_step"):
        parts.append(("来源步骤：" if zh else "Source step: ") + f"Step {job['source_step']}")
    if job.get("theme"):
        parts.append(("总体主题：" if zh else "Theme: ") + str(job["theme"]))
    if job.get("purpose"):
        parts.append(("目的：" if zh else "Purpose: ") + str(job["purpose"]))
    if job.get("logic"):
        parts.append(("逻辑链：" if zh else "Logic: ") + str(job["logic"]))
    panels = job.get("panels") or []
    if panels and isinstance(panels[0], dict):
        p0 = panels[0]
        if p0.get("design"):
            parts.append(("设计：" if zh else "Design: ") + str(p0["design"]))
        if p0.get("rationale"):
            parts.append(("存在理由：" if zh else "Rationale: ") + str(p0["rationale"]))
    if job.get("expected_observation"):
        parts.append(("方案预期观察：" if zh else "Planned observation: ") + str(job["expected_observation"]))
    if facts:
        parts.append(("结果文件事实：" if zh else "File facts: ") + "；".join(facts))
    if job.get("style_note"):
        parts.append(str(job["style_note"]))
    parts.append(
        ("图注只陈述方案要求与文件计数，不把预期观察当成已证实结论。" if zh else "Caption states the plan and file counts only.")
    )
    return "\n".join(parts)


def _color_keys_for_job(
    plot_type: str,
    data_dir: Path,
    metadata_csv: str | Path | None,
) -> list[str]:
    """首次出图的 palette 键（分组名/语义色键），失败时返回空表示用默认色序。"""
    from web_frontend.backend.plot_edit_service import _color_keys_for_plot

    upload = Path(metadata_csv).parent if metadata_csv else data_dir
    try:
        return _color_keys_for_plot(plot_type, data_dir, upload)
    except Exception:
        return []


def render_jobs(
    jobs: list[dict[str, Any]],
    *,
    output_dir: Path,
    metadata_csv: str | Path | None,
    language: str = "zh",
    goal_text: str = "",
    project_root: Path | None = None,
    use_literature: bool = True,
    use_existing_when_available: bool = False,
) -> list[dict[str, Any]]:
    figures_dir = Path(output_dir) / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[dict[str, Any]] = []
    results_root = Path(output_dir).parent

    sticky_skill_ids: list[str] = []
    metadata_columns: list[str] = []
    if use_literature:
        from web_frontend.backend.literature_plot_knowledge import load_sticky_literature_skills

        sticky_skill_ids = load_sticky_literature_skills(results_root)
    if metadata_csv:
        try:
            from web_frontend.backend.session_metadata import list_metadata_columns

            metadata_columns = [
                str(c["name"]) for c in list_metadata_columns(Path(metadata_csv))
            ]
        except Exception:
            metadata_columns = []

    for index, job in enumerate(jobs, start=1):
        item = dict(job)
        fig_id = str(item.get("figure_id") or f"Figure {index}")
        slug = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in fig_id).strip("_") or f"figure_{index}"
        stem = item.get("stem") or item.get("plot_type") or "plot"
        png_path = figures_dir / f"{slug}__{stem}.png"
        item["png"] = str(png_path)
        item["svg"] = str(png_path.with_suffix(".svg"))
        item["facts"] = []
        item["caption"] = ""

        existing_png = item.get("existing_png")
        plot_type = str(item.get("plot_type") or "")
        if use_existing_when_available and plot_type:
            from web_frontend.backend.agent_c.figure_data_narrative import plot_data_files_available
            from web_frontend.backend.agent_c.report_view import preferred_png_for_plot_type

            csv_ready = item.get("status") != "missing_data" or plot_data_files_available(
                results_root, plot_type
            )
            if csv_ready:
                preferred = preferred_png_for_plot_type(
                    results_root,
                    plot_type,
                    fallback=existing_png or item.get("png"),
                )
                if preferred:
                    existing_png = str(preferred)
        if (
            use_existing_when_available
            and existing_png
            and Path(existing_png).is_file()
        ):
            facts = extract_figure_facts(plot_type, Path(item.get("data_dir") or existing_png).parent)
            item["facts"] = facts
            item["png"] = str(Path(existing_png).resolve())
            item["status"] = "copied_existing"
            item["missing_reason"] = None
            item["caption"] = _build_caption(item, facts, language)
            rendered.append(item)
            continue

        if item.get("status") != "ready":
            item["caption"] = _build_caption(item, [], language)
            rendered.append(item)
            continue

        plot_type = str(item.get("plot_type") or "")
        data_dir = Path(item["data_dir"])
        spec = get_plot_spec(plot_type)
        if not spec:
            item["status"] = "unsupported"
            item["missing_reason"] = f"C 侧尚未注册图类型: {plot_type}"
            item["caption"] = _build_caption(item, [], language)
            rendered.append(item)
            continue

        if plot_type in {"pca", "plsda"} and not metadata_csv:
            item["status"] = "missing_metadata"
            item["missing_reason"] = "PCA/PLS-DA 需要 metadata.csv 才能按样本着色"
            item["caption"] = _build_caption(item, [], language)
            rendered.append(item)
            continue

        hint = item.get("plot_config_hint") if isinstance(item.get("plot_config_hint"), dict) else {}
        config, style = build_initial_plot_config(
            plot_type=plot_type,
            plan_hint=hint,
            title=item.get("title") or spec.default_title,
            color_keys=_color_keys_for_job(plot_type, data_dir, metadata_csv),
            goal_text=goal_text,
            project_root=project_root,
            use_literature=use_literature,
            weak_titles=[fig_id, plot_type, spec.default_title, item.get("stem") or ""],
            sticky_skill_ids=sticky_skill_ids,
            metadata_columns=metadata_columns,
        )
        item["literature_style"] = {
            "source": style.get("source"),
            "journal": style.get("journal"),
            "matched": style.get("matched") or [],
            "applied_fields": style.get("applied_fields") or [],
            "warnings": style.get("warnings") or [],
        }
        item["style_note"] = style_provenance_line(style, language=language)
        facts = extract_figure_facts(plot_type, data_dir)
        item["facts"] = facts

        def _fallback_png(target: Path, ptype: str = plot_type, ddir: Path = data_dir, cfg: dict = config) -> None:
            from web_frontend.backend.plot_edit_service import PlotEditError, _render_and_build_echarts

            upload = Path(metadata_csv).parent if metadata_csv else ddir
            try:
                _render_and_build_echarts(
                    plot_type=ptype,
                    data_dir=ddir,
                    upload_dir=upload,
                    plot_config=cfg,
                    output_path=target,
                )
            except PlotEditError:
                existing = item.get("existing_png")
                if existing and Path(existing).is_file():
                    target.write_bytes(Path(existing).read_bytes())
                else:
                    raise

        try:
            from web_frontend.backend.agent_c.tea_paper_plots import (
                TEA_PAPER_PLOT_TYPES,
                render_tea_paper_plot,
            )

            if plot_type in TEA_PAPER_PLOT_TYPES:
                render_tea_paper_plot(
                    plot_type,
                    data_dir,
                    png_path,
                    config,
                )
                item["status"] = "rendered"
                item["renderer"] = "tea_paper_matplotlib"
                item["caption"] = _build_caption(item, facts, language)
                rendered.append(item)
                continue

            vega = build_vegalite_spec(
                plot_type=plot_type,
                data_dir=data_dir,
                metadata_csv=metadata_csv,
                plot_config=config,
            )
            write_semantic_outputs(
                png_path=png_path,
                plot_config=config,
                vega_spec=vega,
                source_rel=_rel_maybe(data_dir, png_path),
                png_renderer=lambda p: _fallback_png(p),
            )
            item["status"] = "rendered"
            item["plot_config"] = str(png_path.with_suffix(".plot_config.json"))
        except Exception as exc:
            existing = item.get("existing_png")
            if existing and Path(existing).is_file():
                png_path.write_bytes(Path(existing).read_bytes())
                item["status"] = "copied_existing"
                item["missing_reason"] = f"语义渲染失败，沿用 B 已有 PNG: {exc}"
            else:
                item["status"] = "render_failed"
                item["missing_reason"] = str(exc)
        item["caption"] = _build_caption(item, facts, language)
        if png_path.is_file():
            item["png"] = str(png_path)
            svg = png_path.with_suffix(".svg")
            item["svg"] = str(svg) if svg.is_file() else None
        rendered.append(item)
    return rendered


def _rel_maybe(data_dir: Path, png: Path) -> str:
    try:
        return str(png.relative_to(data_dir)).replace("\\", "/")
    except ValueError:
        return png.name


def write_captions_json(figures: list[dict[str, Any]], output_dir: Path) -> Path:
    path = Path(output_dir) / "captions.json"
    payload = [
        {
            "figure_id": f.get("figure_id"),
            "plot_type": f.get("plot_type"),
            "status": f.get("status"),
            "png": f.get("png"),
            "caption": f.get("caption"),
            "facts": f.get("facts") or [],
            "missing_reason": f.get("missing_reason"),
        }
        for f in figures
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
