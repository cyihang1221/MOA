"""按方案把 B 的结果渲染成科研图。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from web_frontend.backend.literature_figure_style import (
    build_initial_plot_config,
    style_provenance_line,
)
from web_frontend.backend.b_paper_contract import is_paper_strict
from web_frontend.backend.plot_edit_registry import get_plot_spec
from web_frontend.backend.semantic_plot_renderer import (
    build_vegalite_spec,
    write_semantic_metadata_files,
    write_semantic_outputs,
)


def _inventory_file_names(inventory: dict[str, Any]) -> dict[str, dict]:
    """文件名（小写）→ plottable 条目（用于 source_files 优先匹配）。"""
    index: dict[str, dict] = {}
    for item in inventory.get("plottable") or []:
        for fname in item.get("data_files") or []:
            index[str(fname).lower()] = item
    return index


def _file_map_record(inventory: dict[str, Any], filename: str) -> dict[str, Any] | None:
    name = str(filename or "").split("/")[-1]
    rec = (inventory.get("file_map") or {}).get(name)
    if isinstance(rec, dict):
        return rec
    return None


def _pick_plottable(
    plot_type: str,
    *,
    by_type: dict[str, list[dict]],
    file_index: dict[str, dict],
    source_files: list[str],
    used: set[str],
    inventory: dict[str, Any] | None = None,
) -> dict | None:
    """优先按 source_files 走文件契约；有点名文件时禁止用同型其它实验表顶替。"""
    inv = inventory or {}
    file_map = inv.get("file_map") or {}
    if source_files and file_map:
        resolved: dict[str, str] = {}
        missing: list[str] = []
        for sf in source_files:
            rec = _file_map_record(inv, sf)
            if rec and rec.get("status") == "present" and rec.get("path"):
                resolved[str(sf).split("/")[-1]] = str(rec["path"])
            else:
                missing.append(str(sf).split("/")[-1])
        spec = get_plot_spec(plot_type)
        mode = spec.data_mode if spec else "all"
        paper_missing = [name for name in missing if is_paper_strict(name)]
        ok = bool(resolved) if mode == "any" else not missing
        if paper_missing and not resolved:
            ok = False
        if ok:
            contract_dir = inv.get("contract_dir")
            data_dir = contract_dir or str(Path(next(iter(resolved.values()))).parent)
            key = f"{plot_type}:{data_dir}:{'|'.join(sorted(resolved))}"
            if key not in used:
                used.add(key)
                return {
                    "plot_type": plot_type,
                    "stem": (spec.stem_prefix if spec else plot_type),
                    "title": spec.default_title if spec else plot_type,
                    "data_dir": data_dir,
                    "data_files": resolved,
                    "existing_png": None,
                    "missing_files": missing,
                }
        # 点名了论文专用文件却没找到：不要退回 mixOmics 同型图
        if paper_missing or (source_files and not resolved):
            return None
    for sf in source_files:
        base = str(sf).split("/")[-1].lower()
        hit = file_index.get(base)
        if hit and str(hit.get("plot_type")) == plot_type:
            key = f"{hit['plot_type']}:{hit['data_dir']}"
            if key not in used:
                used.add(key)
                return hit
    pool = by_type.get(plot_type) or []
    if source_files:
        return None
    for item in pool:
        key = f"{item['plot_type']}:{item['data_dir']}"
        if key in used:
            continue
        used.add(key)
        return item
    return pool[0] if pool else None


# 方案没点名时仍要出的投稿主图（B 已写出对应 CSV）。
CORE_PUBLICATION_PLOT_TYPES = frozenset(
    {
        "pca",
        "plsda",
        "volcano",
        "vip_bar",
        "heatmap_vip",
        "network_topology",
        "plsda_permutation",
    }
)


def _supplement_core_publication_jobs(
    jobs: list[dict[str, Any]],
    plottable: list[dict[str, Any]],
    used: set[str],
) -> None:
    """B 已有 CSV 的主图，即使方案漏写也补进出图清单。每种图只补一张。"""
    ready = {str(job.get("plot_type") or "") for job in jobs if job.get("status") == "ready"}
    for item in plottable:
        plot_type = str(item.get("plot_type") or "")
        if plot_type not in CORE_PUBLICATION_PLOT_TYPES or plot_type in ready:
            continue
        key = f"{plot_type}:{item.get('data_dir')}"
        if key in used:
            continue
        used.add(key)
        ready.add(plot_type)
        jobs.append(
            {
                "figure_id": "",
                "title": item.get("title") or plot_type,
                "plot_type": plot_type,
                "stem": item.get("stem") or "",
                "theme": "",
                "logic": "",
                "purpose": "方案未点名；B 已写出对应 CSV，按投稿主图补出",
                "expected_observation": "",
                "source_step": 0,
                "source_files": list((item.get("data_files") or {}).keys()),
                "panels": [],
                "plot_config_hint": {},
                "data_dir": item["data_dir"],
                "data_files": item.get("data_files") or {},
                "existing_png": item.get("existing_png"),
                "status": "ready",
                "source": "b_csv",
            }
        )


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
            inventory=inventory,
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
                wet = {
                    "constituent_bar": "tea_constituents.csv",
                    "bioactivity_bar": "bioactivity_assays.csv",
                    "sensory_scores": "sensory_scores.csv",
                    "correlation_heatmap": "correlation_matrix.csv",
                    "paper_fig2_composite": "volatile_pca_scores.csv（禁止用 mixOmics pca_scores.csv 替代）",
                    "paper_fig5_composite": "pca_scores.csv / hca_matrix.csv / plsda_permutation.csv",
                }
                extra = ""
                if plot_type in wet:
                    extra = (
                        f"；缺 `{wet[plot_type]}` 时标为缺失，不伪造五等级图，"
                        "也不宣称复现 Food Chem X 2026"
                    )
                notes = []
                for sf in source_files:
                    rec = _file_map_record(inventory, sf)
                    if rec and rec.get("status") != "present" and rec.get("notes"):
                        notes.append(str(rec["notes"]))
                if notes:
                    extra = extra + "。" + "；".join(dict.fromkeys(notes))
                job["missing_reason"] = (
                    f"方案需要 {plot_type or '未识别图型'}"
                    + (f"（Step {job.get('source_step')} 预期 {', '.join(source_files)}）" if source_files else "")
                    + "，但结果目录没有对应数据文件"
                    + extra
                    if plot_type
                    else "方案未给出可映射的 plot_type"
                )
            jobs.append(job)

    _supplement_core_publication_jobs(jobs, plottable, used)

    if mode in {"available", "plan_then_available"}:
        for item in plottable:
            key = f"{item['plot_type']}:{item['data_dir']}"
            if key in used:
                continue
            # B 侧已有 PNG 时默认不补渲染（报告 existing_figures 会引用）。
            # 论文级代谢组学图仍要进 C，避免软件默认图（无椭圆/孤立点圆环）留在主报告。
            from web_frontend.backend.agent_c.tea_paper_plots import TEA_PAPER_PLOT_TYPES

            publication_rerender = str(item.get("plot_type") or "") in TEA_PAPER_PLOT_TYPES or str(
                item.get("plot_type") or ""
            ) in {
                "pca",
                "plsda",
                "vip_bar",
                "heatmap_vip",
                "volcano",
                "network_topology",
            }
            if item.get("existing_png") and not publication_rerender:
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


def extract_figure_facts(
    plot_type: str,
    data_dir: str | Path,
    *,
    plot_config: dict[str, Any] | None = None,
) -> list[str]:
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
                from web_frontend.backend.plot_theme import DEFAULT_VOLCANO_THRESHOLDS

                df = pd.read_csv(path)
                p_thr = float(DEFAULT_VOLCANO_THRESHOLDS["p"])
                fc_thr = float(DEFAULT_VOLCANO_THRESHOLDS["log2fc"])
                facts.append(f"文件来源 `{path.name}`")
                facts.append(f"阈值 p<{p_thr}、|log2FC|≥{fc_thr}")
                facts.append(f"火山表 {len(df)} 行")
                if "p_value" in df.columns:
                    n_p = int((pd.to_numeric(df["p_value"], errors="coerce") < p_thr).sum())
                    facts.append(f"p<{p_thr} {n_p} 个")
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
                from web_frontend.backend.paper_plot_helpers import vip_threshold_from_config

                df = pd.read_csv(path)
                threshold = vip_threshold_from_config(plot_config)
                facts.append(f"文件来源 `{path.name}`")
                facts.append(f"阈值 VIP>{threshold:g}（计数与作图虚线同一阈值）")
                facts.append(f"VIP 表 {len(df)} 行")
                vcol = next((c for c in df.columns if str(c).lower() == "vip"), None)
                if vcol is not None:
                    n_high = int((pd.to_numeric(df[vcol], errors="coerce") > threshold).sum())
                    facts.append(f"VIP>{threshold:g} 共 {n_high} 个")
    except Exception:
        return facts
    return facts


def _build_caption(
    job: dict[str, Any],
    facts: list[str],
    language: str,
    *,
    metadata_csv: str | Path | None = None,
    data_narrative: dict[str, Any] | None = None,
) -> str:
    fig_id = job.get("figure_id") or "Figure"
    title = job.get("title") or job.get("plot_type") or ""
    zh = (language or "zh").lower().startswith("zh")
    parts = [f"**{fig_id}.** {title}".strip()]
    if job.get("source_step"):
        parts.append(("来源步骤：" if zh else "Source step: ") + f"Step {job['source_step']}")
    from web_frontend.backend.agent_c.nature_distill import (
        caption_contract_and_stats,
        caption_footer,
        evidence_role_from_job,
        figure_claim_from_job,
    )

    claim = figure_claim_from_job(job)
    if claim:
        parts.append(
            ("图件主张（方案，非已证实）：" if zh else "Figure claim (from plan, not confirmed): ")
            + claim
        )
    role = evidence_role_from_job(job)
    if role:
        parts.append(("证据角色：" if zh else "Evidence role: ") + role)
    theme = str(job.get("theme") or "").strip()
    purpose = str(job.get("purpose") or "").strip()
    logic = str(job.get("logic") or "").strip()
    if theme and theme != claim:
        parts.append(("总体主题：" if zh else "Theme: ") + theme)
    if purpose and purpose != claim:
        parts.append(("目的：" if zh else "Purpose: ") + purpose)
    if logic and logic != claim:
        parts.append(("逻辑链：" if zh else "Logic: ") + logic)
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
    parts.extend(
        caption_contract_and_stats(
            job,
            facts,
            zh=zh,
            data_narrative=data_narrative if data_narrative is not None else job.get("data_narrative"),
        )
    )
    if job.get("style_note"):
        parts.append(str(job["style_note"]))
    from web_frontend.backend.paper_plot_helpers import study_design_disclaimer

    disclaimer = study_design_disclaimer(metadata_csv=metadata_csv, language=language)
    if disclaimer:
        parts.append(disclaimer)
    if job.get("status") == "missing_data":
        parts.append(
            "缺数据图未绘制，不补造五等级/湿实验结果。"
            if zh
            else "Missing-data figures are not fabricated."
        )
    parts.append(caption_footer(zh=zh))
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


_DISPLAYED_STYLE_KEYS = (
    "score_style",
    "show_sample_labels",
    "show_grid",
    "ellipse",
    "legend",
)


def displayed_plot_config(results_root: Path, plot_type: str) -> dict[str, Any] | None:
    """右侧文件优先展示的改图稿配置。报告图要和它画成同一张。"""
    from web_frontend.backend.plot_edit_registry import get_plot_spec

    spec = get_plot_spec(plot_type)
    if spec is None or not results_root:
        return None
    path = Path(results_root) / "edited_plots" / f"{spec.stem_prefix}_intent.plot_config.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def align_score_figure_with_displayed_plot(
    item: dict[str, Any],
    results_root: Path,
    metadata_csv: str | Path | None = None,
) -> None:
    """得分图跟右侧文件走同一套样式。

    普通分组分析曾被都匀毛尖配方改成「Non-volatile PCA」并关掉样本名。
    文件栏展示的是带样本名的 PCA Score Plot。这里让报告里重绘的那张沿用同一配置。
    没有改图稿、但分组又不是论文五等级时，去掉论文标题和隐藏标签。
    """
    plot_type = str(item.get("plot_type") or "")
    if plot_type not in {"pca", "plsda"}:
        return
    hint = dict(item.get("plot_config_hint") or {})
    displayed = displayed_plot_config(results_root, plot_type)
    if displayed:
        for key in _DISPLAYED_STYLE_KEYS:
            if key in displayed and displayed[key] is not None:
                hint[key] = displayed[key]
        shown = str(displayed.get("title") or "").strip()
        if shown:
            item["title"] = shown
        item["plot_config_hint"] = hint
        return

    from web_frontend.backend.literature_figure_style import _TITLE_SUGGESTIONS
    from web_frontend.backend.paper_plot_helpers import study_design_disclaimer

    if not study_design_disclaimer(metadata_csv=metadata_csv):
        return
    suggestion = _TITLE_SUGGESTIONS.get(plot_type) or ""
    title = str(item.get("title") or "")
    if suggestion and "non-volatile" in title.lower():
        item["title"] = suggestion
    if hint.get("show_sample_labels") is False:
        hint.pop("show_sample_labels", None)
        item["plot_config_hint"] = hint


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
            from web_frontend.backend.agent_c.tea_paper_plots import TEA_PAPER_PLOT_TYPES

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
            publication_rerender = plot_type in TEA_PAPER_PLOT_TYPES or plot_type in {
                "pca",
                "plsda",
                "vip_bar",
                "heatmap_vip",
                "volcano",
                "network_topology",
            }
        else:
            publication_rerender = False
        if (
            use_existing_when_available
            and existing_png
            and Path(existing_png).is_file()
            and not publication_rerender
        ):
            facts = extract_figure_facts(plot_type, Path(item.get("data_dir") or existing_png).parent)
            item["facts"] = facts
            item["png"] = str(Path(existing_png).resolve())
            item["status"] = "copied_existing"
            item["missing_reason"] = None
            item["caption"] = _build_caption(item, facts, language, metadata_csv=metadata_csv)
            rendered.append(item)
            continue

        if item.get("status") != "ready":
            item["caption"] = _build_caption(item, [], language, metadata_csv=metadata_csv)
            rendered.append(item)
            continue

        plot_type = str(item.get("plot_type") or "")
        data_dir = Path(item["data_dir"])
        spec = get_plot_spec(plot_type)
        if not spec:
            item["status"] = "unsupported"
            item["missing_reason"] = f"C 侧尚未注册图类型: {plot_type}"
            item["caption"] = _build_caption(item, [], language, metadata_csv=metadata_csv)
            rendered.append(item)
            continue

        if plot_type in {"pca", "plsda"} and not metadata_csv:
            item["status"] = "missing_metadata"
            item["missing_reason"] = "PCA/PLS-DA 需要 metadata.csv 才能按样本着色"
            item["caption"] = _build_caption(item, [], language, metadata_csv=metadata_csv)
            rendered.append(item)
            continue

        align_score_figure_with_displayed_plot(item, results_root, metadata_csv)
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
            use_ai_style=use_literature,
        )
        item["literature_style"] = {
            "source": style.get("source"),
            "journal": style.get("journal"),
            "matched": style.get("matched") or [],
            "applied_fields": style.get("applied_fields") or [],
            "warnings": style.get("warnings") or [],
        }
        item["style_note"] = style_provenance_line(style, language=language)
        facts = extract_figure_facts(plot_type, data_dir, plot_config=config)
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
                    metadata_csv=metadata_csv,
                )
                try:
                    vega = build_vegalite_spec(
                        plot_type=plot_type,
                        data_dir=data_dir,
                        metadata_csv=metadata_csv,
                        plot_config=config,
                    )
                    write_semantic_metadata_files(
                        png_path=png_path,
                        plot_config=config,
                        vega_spec=vega,
                        source_rel=_rel_maybe(data_dir, png_path),
                    )
                except Exception:
                    pass
                item["status"] = "rendered"
                item["renderer"] = "tea_paper_matplotlib"
                _attach_journal_export(item, png_path)
                item["caption"] = _build_caption(item, facts, language, metadata_csv=metadata_csv)
                rendered.append(item)
                continue

            matplotlib_first = plot_type in {
                "pca",
                "plsda",
                "vip_bar",
                "heatmap_vip",
                "volcano",
                "network_topology",
            }
            if matplotlib_first:
                _fallback_png(png_path)
                try:
                    vega = build_vegalite_spec(
                        plot_type=plot_type,
                        data_dir=data_dir,
                        metadata_csv=metadata_csv,
                        plot_config=config,
                    )
                    write_semantic_metadata_files(
                        png_path=png_path,
                        plot_config=config,
                        vega_spec=vega,
                        source_rel=_rel_maybe(data_dir, png_path),
                    )
                except Exception:
                    pass
                item["status"] = "rendered"
                from web_frontend.backend.r_plot_backend import R_PLOT_TYPES

                item["renderer"] = "r" if plot_type in R_PLOT_TYPES else "matplotlib_publication"
                item["plot_config"] = str(png_path.with_name(f"{png_path.stem}.plot_config.json"))
                if plot_type in R_PLOT_TYPES:
                    from web_frontend.backend.plot_parameter_record import attach_parameter_record

                    attach_parameter_record(png_path, item["plot_config"])
                _attach_journal_export(item, png_path)
            else:
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
        item["caption"] = _caption_with_record(
            item,
            _build_caption(item, facts, language, metadata_csv=metadata_csv),
            png_path,
        )
        if png_path.is_file():
            item["png"] = str(png_path)
            svg = png_path.with_suffix(".svg")
            item["svg"] = str(svg) if svg.is_file() else None
            _attach_journal_export(item, png_path)
        rendered.append(item)
    return rendered


def _attach_journal_export(item: dict[str, Any], png_path: Path) -> None:
    from web_frontend.backend.agent_c.nature_distill.journal_export import load_journal_export

    payload = load_journal_export(png_path)
    if not payload:
        return
    item["journal_export"] = payload
    pdf = payload.get("pdf") or str(Path(png_path).with_suffix(".pdf"))
    if pdf and Path(str(pdf)).is_file():
        item["pdf"] = str(pdf)
    journal_svg = payload.get("svg")
    if journal_svg and Path(str(journal_svg)).is_file():
        item["journal_svg"] = str(journal_svg)


def _caption_with_record(item: dict[str, Any], caption: str, png_path: Path) -> str:
    """分子网络不改作图软件说明。其他图只有 C 写出参数记录时才补图注。"""
    plot_type = str(item.get("plot_type") or "")
    if plot_type == "network_topology" or not png_path.is_file():
        return caption
    from web_frontend.backend.plot_parameter_record import build_parameter_record, enrich_caption

    record = build_parameter_record(png_path)
    if not record:
        return caption
    item["parameter_record"] = record
    detail = record.get("detail") if isinstance(record.get("detail"), dict) else {}
    return enrich_caption(caption, plot_type, record, score_style=str(detail.get("score_style") or ""))


def refresh_figure_captions(
    figures: list[dict[str, Any]],
    *,
    language: str = "zh",
    metadata_csv: str | Path | None = None,
) -> None:
    """叙事补全后重写图注，把统计清单和文件来源收进 caption。"""
    for fig in figures:
        facts = list(fig.get("facts") or [])
        png_path = Path(str(fig.get("png") or ""))
        fig["caption"] = _caption_with_record(
            fig,
            _build_caption(
                fig,
                facts,
                language,
                metadata_csv=metadata_csv,
                data_narrative=fig.get("data_narrative"),
            ),
            png_path,
        )


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
            "journal_export": f.get("journal_export"),
        }
        for f in figures
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
