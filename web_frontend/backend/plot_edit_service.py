"""Web 端 Agent 改图服务：解析意图 → 合并 plot_config → matplotlib 重绘。"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from src.platform_utils import normalize_display_path

from web_frontend.backend.plot_edit_agent import parse_plot_edit_instruction
from web_frontend.backend.plot_edit_registry import (
    PLOT_STEM_ALIASES,
    extract_plot_edit_tasks,
    get_plot_spec,
    is_agent_plot_editable_stem,
    list_editable_plots,
    plot_spec_data_ready,
    plot_type_from_stem,
    resolve_plot_data_file,
    resolve_plot_source_rel,
)
from web_frontend.backend.plot_renderer import (
    build_echarts_bar,
    build_echarts_histogram,
    build_echarts_option,
    build_echarts_volcano,
    load_scores_and_groups,
    render_cosine_hist_png,
    render_degree_hist_png,
    render_family_size_png,
    render_score_plot_png,
    render_volcano_plot_png,
    save_plot_sidecars,
    _family_size_payload,
)
from web_frontend.backend.literature_figure_style import build_initial_plot_config
from web_frontend.backend.plot_theme import (
    diff_plot_config,
    merge_plot_config,
    normalize_plot_config,
    plot_config_path_for_png,
)
from web_frontend.backend.session_metadata import list_metadata_columns, resolve_metadata_csv
from web_frontend.backend.session_storage import edited_plots_dir, session_upload_dir, session_work_dir
from web_frontend.backend.plot_versioning import (
    canonical_plot_base,
    find_effective_plot_rel,
    find_original_plot_rel,
    stable_intent_filename,
    write_current_pointer,
)
from web_frontend.backend.semantic_plot_renderer import (
    build_vegalite_spec,
    is_vl_convert_available,
    write_semantic_metadata_files,
    write_semantic_outputs,
    write_svg_sidecar,
)


class PlotEditError(Exception):
    pass


def ensure_default_plot_configs(
    directory: str | Path,
    *,
    upload_dir: str | Path | None = None,
    goal_text: str = "",
    use_literature: bool = True,
    project_root: str | Path | None = None,
) -> list[Path]:
    """为可语义编辑的 PNG 补写 plot_config / Vega-Lite / SVG sidecar。

    递归扫描子目录（如 fbmn/、ms2lda_results/），跳过 edited_plots / merged_figures。

    首次写 sidecar 时套用文献/发表级样式（``goal_text`` 提供匹配上下文）；
    已存在的 sidecar 视为用户已确认的样式，不再覆盖。
    """
    from web_frontend.backend.session_storage import EDITED_PLOTS_SUBDIR, MERGED_FIGURES_SUBDIR

    root = Path(directory)
    if not root.is_dir():
        return []
    written: list[Path] = []
    upload = Path(upload_dir) if upload_dir else None
    metadata_csv = None
    if upload is not None:
        try:
            metadata_csv = resolve_metadata_csv(upload)
        except Exception:
            metadata_csv = None

    png_files = []
    for png in sorted(root.rglob("*.png")):
        try:
            rel_parts = png.relative_to(root).parts
        except ValueError:
            continue
        if rel_parts and rel_parts[0] in {EDITED_PLOTS_SUBDIR, MERGED_FIGURES_SUBDIR}:
            continue
        if png.stem.endswith("_edited") or png.stem.startswith("tmp_"):
            continue
        png_files.append(png)

    for png in png_files:
        stem = png.stem
        if not is_agent_plot_editable_stem(stem):
            continue
        plot_type = plot_type_from_stem(stem)
        if not plot_type:
            continue
        spec = get_plot_spec(plot_type)
        if not spec:
            continue
        data_root = png.parent
        if not plot_spec_data_ready(data_root, spec):
            continue

        config_path = Path(plot_config_path_for_png(str(png)))
        color_keys: list[str] = []
        try:
            if upload is not None:
                color_keys = _color_keys_for_plot(plot_type, data_root, upload)
            elif plot_type == "volcano":
                color_keys = [
                    "upregulated",
                    "downregulated",
                    "nonsignificant",
                    "threshold_color",
                ]
            elif plot_type == "family_size":
                nodes = resolve_plot_data_file(data_root, "network_nodes.csv")
                labels, _, _ = _family_size_payload(nodes) if nodes else ([], [], [])
                color_keys = labels
            elif plot_type in ("degree_hist", "cosine_hist", "precursor_mass_diff", "pearson_hist"):
                color_keys = ["histogram_color", "threshold_color", "median_color", "scatter_color"]
            elif plot_type == "vip_bar":
                color_keys = ["bar_color"]
            elif plot_type == "mass2motif_fragments":
                color_keys = ["fragment_color"]
            elif plot_type == "annotation_propagation":
                color_keys = ["direct", "propagated", "unknown"]
            elif plot_type == "kegg_barplot":
                color_keys = ["bar_color"]
            elif plot_type == "network_topology":
                color_keys = _topology_family_keys(data_root)
        except Exception:
            color_keys = []

        existing = None
        if config_path.is_file():
            try:
                existing = json.loads(config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = None
        if isinstance(existing, dict):
            config = normalize_plot_config(
                existing,
                plot_type=plot_type,
                color_keys=color_keys,
            )
            lit = existing.get("literature_style")
            if isinstance(lit, dict):
                config["literature_style"] = lit
        else:
            config, _style = build_initial_plot_config(
                plot_type=plot_type,
                color_keys=color_keys,
                goal_text=goal_text,
                project_root=Path(project_root) if project_root else None,
                use_literature=use_literature,
            )
        try:
            config["source_rel"] = png.relative_to(root).as_posix()
        except ValueError:
            config["source_rel"] = png.name
        try:
            vega_spec = build_vegalite_spec(
                plot_type=plot_type,
                data_dir=data_root,
                metadata_csv=metadata_csv if plot_type in {"pca", "plsda"} else None,
                plot_config=config,
            )
        except Exception:
            # 数据不齐时至少写 plot_config，便于前端打开后再报错
            if not config_path.is_file():
                config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
                written.append(config_path)
            continue

        upload_root = upload if upload is not None else data_root

        def _png_renderer(target: Path, *, ptype: str = plot_type, ddir: Path = data_root, cfg: dict = config) -> None:
            _render_and_build_echarts(
                plot_type=ptype,
                data_dir=ddir,
                upload_dir=upload_root,
                plot_config=cfg,
                output_path=target,
            )

        try:
            write_semantic_outputs(
                png_path=png,
                plot_config=config,
                vega_spec=vega_spec,
                source_rel=config.get("source_rel"),
                png_renderer=_png_renderer,
            )
        except Exception:
            write_semantic_metadata_files(
                png_path=png,
                plot_config=config,
                vega_spec=vega_spec,
                source_rel=config.get("source_rel"),
            )
            write_svg_sidecar(vega_spec, png)
        written.append(config_path)

    # vip_scores.csv 存在但无 PNG 时，生成可 SVG 编辑的 VIP 柱状图
    for vip_csv in root.rglob("vip_scores.csv"):
        if any(part in {EDITED_PLOTS_SUBDIR, MERGED_FIGURES_SUBDIR} for part in vip_csv.parts):
            continue
        vip_png = vip_csv.with_name("vip_scores.png")
        if vip_csv.is_file() and not vip_png.is_file():
            try:
                config, _ = build_initial_plot_config(
                    plot_type="vip_bar",
                    color_keys=["bar_color"],
                    goal_text=goal_text,
                    project_root=Path(project_root) if project_root else None,
                    use_literature=use_literature,
                )
                config["source_rel"] = vip_png.name
                vega_spec = build_vegalite_spec(
                    plot_type="vip_bar",
                    data_dir=vip_csv.parent,
                    metadata_csv=None,
                    plot_config=config,
                )
                write_semantic_outputs(
                    png_path=vip_png,
                    plot_config=config,
                    vega_spec=vega_spec,
                    source_rel=vip_png.name,
                )
                written.append(Path(plot_config_path_for_png(str(vip_png))))
            except Exception:
                pass
    return written


def _load_existing_config(png_path: Path) -> dict[str, Any] | None:
    sidecar = Path(plot_config_path_for_png(png_path))
    if not sidecar.is_file():
        return None
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _resolve_output_png(
    output_root: Path,
    source: Path,
    filename: str | None,
    *,
    overwrite: bool = False,
) -> Path:
    edit_dir = edited_plots_dir(output_root)
    stem = Path(filename or f"{source.stem}_edited.png").stem
    target = edit_dir / f"{stem}.png"
    if target.exists() and not overwrite:
        target = edit_dir / f"{stem}_{uuid.uuid4().hex[:8]}.png"
    return target


def _validated_source(
    output_root: Path,
    source_rel: str,
    *,
    hint_message: str | None = None,
) -> Path:
    rel = str(source_rel or "").strip().lstrip("/")
    if rel:
        direct = (output_root / rel).resolve()
        try:
            direct.relative_to(output_root.resolve())
            if direct.is_file() and direct.suffix.lower() == ".png":
                return direct
        except ValueError:
            pass
    try:
        # 已定位到具体文件时不要再用 instruction 别名重解析，避免跳回分析原图
        canonical = resolve_plot_source_rel(
            output_root,
            source_rel,
            hint_message=None if rel else hint_message,
        )
    except ValueError as exc:
        raise PlotEditError(str(exc)) from exc
    source = (output_root / canonical).resolve()
    try:
        source.relative_to(output_root.resolve())
    except ValueError as exc:
        raise PlotEditError("只能编辑 outputspace 中的图片") from exc
    if not source.is_file() or source.suffix.lower() != ".png":
        raise PlotEditError("source_rel 必须是 output 目录下的 PNG 文件")
    return source


def _resolve_source_and_data_dir(
    output_root: Path,
    source_rel: str,
    existing_config: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    source = _validated_source(output_root, source_rel, hint_message=None)

    original_rel = (existing_config or {}).get("source_rel")
    if isinstance(original_rel, str) and original_rel.strip():
        original = (output_root / original_rel.strip().lstrip("/")).resolve()
        try:
            original.relative_to(output_root)
        except ValueError:
            original = source
        if original.is_file():
            return source, original.parent
    return source, source.parent


def get_semantic_plot_payload(
    *,
    project_root: Path,
    storage_slug: str,
    source_rel: str,
    plot_config_patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load normalized semantic config and a self-contained Vega-Lite spec."""
    output_root = session_work_dir(project_root, storage_slug).resolve()
    canonical_rel = resolve_plot_source_rel(output_root, source_rel)
    initial_source = _validated_source(output_root, canonical_rel)
    existing = _load_existing_config(initial_source)
    source, data_dir = _resolve_source_and_data_dir(output_root, canonical_rel, existing)
    plot_type = plot_type_from_stem(source.stem)
    if plot_type is None and existing:
        plot_type = str(existing.get("plot_type") or "") or None
    if plot_type is None or not get_plot_spec(plot_type):
        raise PlotEditError(f"暂不支持语义编辑：{source.name}")

    upload_dir = session_upload_dir(project_root, storage_slug)
    color_keys = _color_keys_for_plot(plot_type, data_dir, upload_dir, existing if isinstance(existing, dict) else None)
    config = normalize_plot_config(existing, plot_type=plot_type, color_keys=color_keys)
    if plot_config_patch:
        config = merge_plot_config(config, plot_config_patch)
        color_keys = _color_keys_for_plot(plot_type, data_dir, upload_dir, config)
        config = normalize_plot_config(config, plot_type=plot_type, color_keys=color_keys)
    else:
        color_keys = _color_keys_for_plot(plot_type, data_dir, upload_dir, config)
        config = normalize_plot_config(config, plot_type=plot_type, color_keys=color_keys)

    metadata_csv = None
    metadata_columns: list[dict[str, Any]] = []
    color_by_columns: list[str] = []
    if plot_type in {"pca", "plsda"}:
        metadata_csv = resolve_metadata_csv(upload_dir)
        try:
            metadata_columns = list_metadata_columns(metadata_csv)
        except Exception:
            metadata_columns = []
    elif plot_type == "network_topology":
        color_by_columns = _topology_color_by_columns(data_dir)
    vega_spec = build_vegalite_spec(
        plot_type=plot_type,
        data_dir=data_dir,
        metadata_csv=metadata_csv,
        plot_config=config,
    )
    return {
        "source_rel": canonical_rel,
        "plot_type": plot_type,
        "color_keys": color_keys,
        "plot_config": config,
        "vega_spec": vega_spec,
        "metadata_columns": metadata_columns,
        "color_by_columns": color_by_columns,
    }


def _topology_color_by_columns(data_dir: Path) -> list[str]:
    """拓扑图可选着色列（layout + 可 join 的节点属性）。"""
    from web_frontend.backend.semantic_plot_renderer import (
        _join_topology_node_attrs,
        _network_layout_frame,
    )

    try:
        layout = _network_layout_frame(data_dir, {})
        layout = _join_topology_node_attrs(data_dir, layout)
    except Exception:
        return ["family"]
    preferred = (
        "family",
        "chemical_category",
        "degree",
        "log2FC",
        "molecular_family",
        "category_confidence",
    )
    skip = {"node_id", "x", "y", "_join_id"}
    found: list[str] = []
    for col in preferred:
        if col in layout.columns and col not in found:
            found.append(col)
    for col in layout.columns:
        name = str(col)
        if name in skip or name in found:
            continue
        # 跳过坐标/过多唯一值的纯数值 id
        if name.lower().endswith("_id"):
            continue
        found.append(name)
    return found or ["family"]


def _topology_family_keys(data_dir: Path) -> list[str]:
    """拓扑图调色键：优先 network_layout.csv 的 family，缺失时回落节点表。"""
    layout = data_dir / "network_layout.csv"
    if layout.is_file():
        frame = pd.read_csv(layout)
        if "family" in frame.columns:
            return list(dict.fromkeys(str(v) for v in frame["family"].fillna("singleton")))
    nodes = resolve_plot_data_file(data_dir, "network_nodes.csv")
    if nodes is None:
        return []
    frame = pd.read_csv(nodes)
    for column in ("family", "molecular_family"):
        if column in frame.columns:
            return list(dict.fromkeys(str(v) for v in frame[column].fillna("singleton")))
    return []


def _color_keys_for_plot(
    plot_type: str,
    data_dir: Path,
    upload_dir: Path,
    plot_config: dict[str, Any] | None = None,
) -> list[str]:
    if plot_type in ("pca", "plsda"):
        from web_frontend.backend.plot_renderer import score_color_meta

        spec = get_plot_spec(plot_type)
        if not spec:
            return []
        scores_path = resolve_plot_data_file(data_dir, spec.data_files[0]) or (
            data_dir / spec.data_files[0]
        )
        metadata_csv = resolve_metadata_csv(upload_dir)
        cfg = dict(plot_config) if isinstance(plot_config, dict) else {}
        _, groups, _, _ = load_scores_and_groups(scores_path, metadata_csv, plot_config=cfg)
        # 回写解析后的 color_by / color_type
        if isinstance(plot_config, dict):
            plot_config["color_by"] = cfg.get("color_by", plot_config.get("color_by"))
            plot_config["color_type"] = cfg.get("color_type", plot_config.get("color_type"))
            plot_config["cluster"] = cfg.get("cluster")
        _legend, color_type = score_color_meta(cfg)
        if color_type == "quantitative":
            return []
        seen: set[str] = set()
        ordered: list[str] = []
        for g in groups:
            gs = str(g)
            if gs not in seen:
                seen.add(gs)
                ordered.append(gs)
        return ordered
    if plot_type == "volcano":
        return [
            "upregulated",
            "downregulated",
            "nonsignificant",
            "threshold_color",
        ]
    if plot_type == "family_size":
        nodes = resolve_plot_data_file(data_dir, "network_nodes.csv")
        if nodes is None:
            return []
        labels, _, _ = _family_size_payload(nodes)
        return labels
    if plot_type in ("degree_hist", "cosine_hist", "precursor_mass_diff", "pearson_hist"):
        return ["histogram_color", "threshold_color", "median_color", "scatter_color"]
    if plot_type == "vip_bar":
        return ["bar_color"]
    if plot_type == "mass2motif_overview":
        return []
    if plot_type == "mass2motif_fragments":
        return ["fragment_color", "loss_color"]
    if plot_type in ("motif_spectrum_heatmap", "heatmap_vip"):
        return []
    if plot_type in ("chemical_class_distribution", "family_chemical_consensus"):
        try:
            counts = None
            from web_frontend.backend.semantic_plot_renderer import _chemical_category_counts

            if plot_type == "chemical_class_distribution":
                counts = _chemical_category_counts(data_dir)
                return [str(v) for v in counts["chemical_category"].tolist()]
            path = resolve_plot_data_file(data_dir, "chemical_class_distribution.csv")
            if path is None:
                return []
            frame = pd.read_csv(path)
            if "chemical_category" in frame.columns:
                return list(dict.fromkeys(str(v) for v in frame["chemical_category"].fillna("unknown")))
        except Exception:
            return []
        return []
    if plot_type == "annotation_propagation":
        return ["direct", "propagated", "unknown"]
    if plot_type in ("kegg_bubble", "kegg_dotplot"):
        return []
    if plot_type == "kegg_barplot":
        return ["bar_color"]
    if plot_type == "fbmn_group_intensity":
        try:
            path = resolve_plot_data_file(data_dir, "fbmn_group_intensity.csv")
            if path is None:
                return []
            frame = pd.read_csv(path)
            if "group" in frame.columns:
                return list(dict.fromkeys(str(v) for v in frame["group"].tolist()))
        except Exception:
            return []
        return []
    if plot_type == "mass2motif_network":
        return ["motif_color", "spectrum_color", "edge_color"]
    if plot_type == "network_topology":
        return _topology_family_keys(data_dir)
    if plot_type == "splot":
        return ["significant", "nonsignificant"]
    if plot_type == "opls_outlier":
        return ["outlier", "normal", "threshold_color"]
    if plot_type in ("roc_auc_hist", "log2fc_hist"):
        return ["histogram_color", "threshold_color", "median_color"]
    if plot_type == "plsda_permutation":
        return ["r2_color", "q2_color"]
    if plot_type == "significance_venn":
        try:
            path = resolve_plot_data_file(
                data_dir, "statistical_analysis_metax_significance_sets.csv"
            )
            if path is None:
                return []
            frame = pd.read_csv(path)
            if "intersection" in frame.columns:
                sets = [s for s in dict.fromkeys(frame["intersection"].fillna("").astype(str)) if s]
                return sets
        except Exception:
            return []
        return []
    if plot_type in {"constituent_bar", "bioactivity_bar"}:
        filename = (
            "tea_constituents.csv" if plot_type == "constituent_bar" else "bioactivity_assays.csv"
        )
        path = resolve_plot_data_file(data_dir, filename)
        if path is None:
            return []
        frame = pd.read_csv(path)
        if "grade" in frame.columns:
            return list(dict.fromkeys(str(v) for v in frame["grade"].tolist()))
        return []
    if plot_type == "sensory_scores":
        path = resolve_plot_data_file(data_dir, "sensory_scores.csv")
        if path is None:
            return []
        frame = pd.read_csv(path)
        if "attribute" in frame.columns:
            return list(dict.fromkeys(str(v) for v in frame["attribute"].tolist()))
        return []
    if plot_type in {"hca_heatmap", "correlation_heatmap", "relative_abundance_heatmap"}:
        return []
    return []


def _render_and_build_echarts(
    *,
    plot_type: str,
    data_dir: Path,
    upload_dir: Path,
    plot_config: dict[str, Any],
    output_path: Path,
) -> dict[str, Any]:
    spec = get_plot_spec(plot_type)
    if not spec:
        raise PlotEditError(f"未知图类型: {plot_type}")

    if plot_type in ("pca", "plsda"):
        scores_path = data_dir / spec.data_files[0]
        metadata_csv = resolve_metadata_csv(upload_dir)
        scores, groups, samples, axis_names = load_scores_and_groups(
            scores_path, metadata_csv, plot_config=plot_config
        )
        render_score_plot_png(
            scores=scores,
            groups=groups,
            sample_names=samples,
            axis_names=axis_names,
            plot_config=plot_config,
            output_path=output_path,
        )
        return build_echarts_option(
            scores=scores,
            groups=groups,
            sample_names=samples,
            axis_names=axis_names,
            plot_config=plot_config,
        )

    if plot_type == "volcano":
        volcano_csv = resolve_plot_data_file(data_dir, spec.data_files[0])
        if volcano_csv is None:
            raise PlotEditError("缺少 volcano_results.csv")
        if volcano_csv.name == "volcano_results.csv":
            render_volcano_plot_png(volcano_csv, plot_config, output_path)
            return build_echarts_volcano(volcano_csv, plot_config)
        # Agent B 变体表列名不同，matplotlib 回退不适用：复制原图保底
        return _copy_source_png_fallback(plot_type, data_dir, output_path)

    if plot_type == "family_size":
        nodes_csv = resolve_plot_data_file(data_dir, "network_nodes.csv")
        if nodes_csv is None:
            raise PlotEditError("缺少 network_nodes.csv / fbmn_nodes.csv")
        labels, sizes, colors = _family_size_payload(nodes_csv)
        palette = plot_config.get("palette") or {}
        for i, label in enumerate(labels):
            if label in palette:
                colors[i] = palette[label]
        render_family_size_png(nodes_csv, plot_config, output_path)
        return build_echarts_bar(labels, sizes, colors, plot_config)

    if plot_type == "degree_hist":
        nodes_csv = resolve_plot_data_file(data_dir, "network_nodes.csv")
        if nodes_csv is None:
            raise PlotEditError("缺少 network_nodes.csv / fbmn_nodes.csv")
        render_degree_hist_png(nodes_csv, plot_config, output_path)
        df = pd.read_csv(nodes_csv)
        degrees = df["degree"].dropna().astype(float).tolist() if "degree" in df.columns else [1.0] * len(df)
        avg = float(sum(degrees) / len(degrees)) if degrees else 0.0
        return build_echarts_histogram(
            degrees,
            plot_config,
            x_name="Degree",
            vlines=[(avg, "Mean", plot_config.get("colors", {}).get("threshold_color", "#d62728"))],
        )

    if plot_type == "cosine_hist":
        edges_csv = resolve_plot_data_file(data_dir, "network_edges.csv")
        if edges_csv is None:
            raise PlotEditError("缺少 network_edges.csv / fbmn_edges.csv")
        render_cosine_hist_png(edges_csv, plot_config, output_path)
        df = pd.read_csv(edges_csv)
        cosines = df["cosine"].dropna().astype(float).tolist()
        import numpy as np

        median = float(np.median(cosines)) if cosines else 0.0
        return build_echarts_histogram(
            cosines,
            plot_config,
            x_name="Cosine",
            vlines=[
                (0.7, "Threshold", plot_config.get("colors", {}).get("threshold_color", "#d62728")),
                (median, "Median", plot_config.get("colors", {}).get("median_color", "#ff7f0e")),
            ],
        )

    if plot_type == "precursor_mass_diff":
        # PNG 由 vl-convert / 原图回退；此处仅返回空 echarts（语义预览走 Vega）
        import shutil

        source_png = data_dir / "precursor_mass_diff.png"
        if source_png.is_file() and source_png.resolve() != output_path.resolve():
            shutil.copy2(source_png, output_path)
        elif not output_path.is_file():
            raise PlotEditError("缺少 vl-convert 且无法回退渲染: precursor_mass_diff")
        return {}

    from web_frontend.backend.agent_c.tea_paper_plots import TEA_PAPER_PLOT_TYPES, render_tea_paper_plot

    if plot_type in TEA_PAPER_PLOT_TYPES:
        try:
            render_tea_paper_plot(plot_type, data_dir, output_path, plot_config)
            return {}
        except Exception:
            return _copy_source_png_fallback(plot_type, data_dir, output_path)

    # 其余语义图（vip / heatmap / topology / Agent B step8 变体）：
    # 无 matplotlib 回退实现时复制原图，保证 vl-convert 缺失也不中断改图
    return _copy_source_png_fallback(plot_type, data_dir, output_path)


def _copy_source_png_fallback(
    plot_type: str,
    data_dir: Path,
    output_path: Path,
) -> dict[str, Any]:
    import shutil

    candidates: list[str] = []
    spec = get_plot_spec(plot_type)
    if spec:
        candidates.append(spec.stem_prefix)
    candidates.extend(stem for stem, ptype in PLOT_STEM_ALIASES.items() if ptype == plot_type)
    for stem in candidates:
        source_png = data_dir / f"{stem}.png"
        if source_png.is_file() and source_png.resolve() != output_path.resolve():
            shutil.copy2(source_png, output_path)
            return {}
    if output_path.is_file():
        return {}
    raise PlotEditError(f"缺少 vl-convert 且无法回退渲染: {plot_type}")


def apply_plot_config(
    *,
    project_root: Path,
    session_id: str,
    storage_slug: str,
    source_rel: str,
    plot_config_patch: dict[str, Any],
    instruction: str | None = None,
    filename: str | None = None,
    overwrite_intent: bool = True,
) -> dict[str, Any]:
    """语义重绘。默认写入稳定的 ``{base}_intent.png`` 并更新 current 指针，支持连续改图。"""
    output_root = session_work_dir(project_root, storage_slug).resolve()
    # 1) 先按用户/LLM 提示定位「逻辑图」，并升到当前生效版
    try:
        requested_rel = resolve_plot_source_rel(
            output_root, source_rel, hint_message=instruction
        )
    except ValueError:
        requested_rel = str(source_rel or "").strip().lstrip("/")

    info = find_effective_plot_rel(output_root, requested_rel)
    base = info.get("base") or canonical_plot_base(requested_rel)
    effective_rel = info.get("effective_rel") or requested_rel
    original_rel = info.get("original_rel") or find_original_plot_rel(output_root, base)

    # 连续改图：从 effective（intent/edited）读 config；数据目录仍回原始分析图
    edit_source_rel = effective_rel or requested_rel
    initial_source = _validated_source(
        output_root, edit_source_rel, hint_message=None
    )
    base_existing = _load_existing_config(initial_source)

    # data_dir：优先 config.source_rel / original_rel
    data_anchor = (
        str((base_existing or {}).get("source_rel") or "").strip()
        or original_rel
        or edit_source_rel
    )
    source, data_dir = _resolve_source_and_data_dir(
        output_root, data_anchor, base_existing
    )

    stem_for_type = Path(original_rel or edit_source_rel).stem
    stem_for_type = canonical_plot_base(stem_for_type) or stem_for_type
    existing_plot_type = str((base_existing or {}).get("plot_type") or "")
    plot_type = plot_type_from_stem(stem_for_type) or existing_plot_type
    if not get_plot_spec(plot_type or ""):
        raise PlotEditError(
            f"暂不支持语义重绘：{initial_source.name}。"
            "请使用 Agent 通用改图（标题/字号/颜色）。"
        )

    upload_dir = session_upload_dir(project_root, storage_slug)
    color_keys = _color_keys_for_plot(
        plot_type, data_dir, upload_dir, base_existing if isinstance(base_existing, dict) else None
    )

    before_cfg = normalize_plot_config(base_existing, plot_type=plot_type, color_keys=color_keys)
    merged = merge_plot_config(before_cfg, plot_config_patch)
    color_keys = _color_keys_for_plot(plot_type, data_dir, upload_dir, merged)
    merged = normalize_plot_config(merged, plot_type=plot_type, color_keys=color_keys)
    config_diff = diff_plot_config(before_cfg, merged)

    out_name = filename or stable_intent_filename(base or stem_for_type)
    # 稳定 intent 名默认覆盖，避免 hash 分叉
    overwrite = bool(overwrite_intent) and (
        out_name.endswith("_intent.png") or "intent" in Path(out_name).stem
    )
    target_png = _resolve_output_png(
        output_root, initial_source, out_name, overwrite=overwrite
    )
    metadata_csv = resolve_metadata_csv(upload_dir) if plot_type in {"pca", "plsda"} else None
    vega_spec = build_vegalite_spec(
        plot_type=plot_type,
        data_dir=data_dir,
        metadata_csv=metadata_csv,
        plot_config=merged,
    )

    def _render_png_fallback(path: Path) -> None:
        _render_and_build_echarts(
            plot_type=plot_type,
            data_dir=data_dir,
            upload_dir=upload_dir,
            plot_config=merged,
            output_path=path,
        )

    preserved_source = str(
        (base_existing or {}).get("source_rel")
        or original_rel
        or data_anchor
    )
    config_path, vega_path, svg_path, _ = write_semantic_outputs(
        png_path=target_png,
        plot_config=merged,
        vega_spec=vega_spec,
        instruction=instruction,
        source_rel=preserved_source,
        png_renderer=_render_png_fallback,
    )

    stat = target_png.stat()
    rel_png = target_png.relative_to(output_root).as_posix()
    if base:
        write_current_pointer(output_root, base, rel_png)

    result = {
        "file": {
            "name": rel_png,
            "path": normalize_display_path(target_png),
            "size": stat.st_size,
        },
        "plot_config": {
            "name": config_path.relative_to(output_root).as_posix(),
            "path": normalize_display_path(config_path),
            "data": merged,
        },
        "vega": {
            "name": vega_path.relative_to(output_root).as_posix(),
            "path": normalize_display_path(vega_path),
        },
        "source_rel": preserved_source,
        "effective_rel": rel_png,
        "plot_base": base,
        "plot_type": plot_type,
        "config_diff": config_diff,
    }
    if svg_path is not None:
        result["svg"] = {
            "name": svg_path.relative_to(output_root).as_posix(),
            "path": normalize_display_path(svg_path),
        }
    return result



def agent_apply_plot_edit(
    *,
    project_root: Path,
    session_id: str,
    storage_slug: str,
    source_rel: str,
    instruction: str,
    model: str | None = None,
    filename: str | None = None,
    goal_text: str | None = None,
) -> dict[str, Any]:
    output_root = session_work_dir(project_root, storage_slug).resolve()
    try:
        canonical_rel = resolve_plot_source_rel(
            output_root,
            source_rel,
            hint_message=instruction,
        )
    except ValueError:
        # 允许任意输出 PNG（通用改图）
        candidate = (output_root / source_rel).resolve()
        try:
            candidate.relative_to(output_root)
        except ValueError as exc:
            raise PlotEditError(f"无法定位图片：{source_rel}") from exc
        if not candidate.is_file():
            # bare filename search
            matches = list(output_root.rglob(Path(source_rel).name))
            matches = [m for m in matches if m.suffix.lower() == ".png"]
            if not matches:
                raise PlotEditError(f"无法定位图片：{source_rel}")
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            canonical_rel = matches[0].relative_to(output_root).as_posix()
        else:
            canonical_rel = candidate.relative_to(output_root).as_posix()

    # 连续改图：解析当前生效版（intent/edited），而非总是原图
    eff = find_effective_plot_rel(output_root, canonical_rel)
    if eff.get("effective_rel"):
        canonical_rel = eff["effective_rel"]
    base = eff.get("base") or canonical_plot_base(canonical_rel)

    source = _validated_source(output_root, canonical_rel, hint_message=instruction)
    existing = _load_existing_config(source)
    type_stem = canonical_plot_base(Path(eff.get("original_rel") or canonical_rel).stem)
    plot_type = (
        plot_type_from_stem(type_stem)
        or plot_type_from_stem(source.stem)
        or str((existing or {}).get("plot_type") or "")
    )
    upload_dir = session_upload_dir(project_root, storage_slug)
    data_anchor = str((existing or {}).get("source_rel") or "").strip() or (
        eff.get("original_rel") or canonical_rel
    )
    _, data_dir = _resolve_source_and_data_dir(output_root, data_anchor, existing)

    # 语义改图：有 PlotSpec 且数据齐全
    spec = get_plot_spec(plot_type) if plot_type else None
    can_semantic = bool(spec and plot_spec_data_ready(data_dir, spec))
    if can_semantic:
        color_keys = _color_keys_for_plot(
            plot_type, data_dir, upload_dir, existing if isinstance(existing, dict) else None
        )
        current = normalize_plot_config(existing, plot_type=plot_type, color_keys=color_keys)
        metadata_columns: list[str] = []
        if plot_type in {"pca", "plsda"}:
            try:
                metadata_columns = [
                    str(c["name"]) for c in list_metadata_columns(resolve_metadata_csv(upload_dir))
                ]
            except Exception:
                metadata_columns = []
        from web_frontend.backend.literature_evidence import (
            collect_evidence_cards,
            evidence_cards_to_markdown,
            suggest_soft_style_patch,
        )
        from web_frontend.backend.literature_plot_knowledge import (
            load_sticky_literature_skills,
            match_plot_literature,
        )
        from web_frontend.backend.visual_edit_journal import append_journal_event
        from web_frontend.backend.visual_ir import attach_evidence, figure_ir_from_config
        from web_frontend.backend.visual_validation import validate_plot_patch

        lit_style = (current.get("literature_style") or {}) if isinstance(current, dict) else {}
        sticky_skill_ids = list(
            dict.fromkeys(
                [str(s) for s in (lit_style.get("matched") or []) if s]
                + load_sticky_literature_skills(output_root)
            )
        )

        evidence_cards = collect_evidence_cards(
            plot_type=plot_type,
            goal_text=goal_text or "",
            instruction=instruction,
            project_root=project_root,
            sticky_skill_ids=sticky_skill_ids,
        )
        figure_ir = attach_evidence(
            figure_ir_from_config(
                plot_type=plot_type,
                source_rel=canonical_rel,
                plot_config=current,
                data_dir=str(data_dir),
                goal_text=goal_text or "",
            ),
            evidence_cards,
        )
        lit_payload = match_plot_literature(
            goal_text=goal_text or "",
            plot_type=plot_type,
            instruction=instruction,
            source_rel=canonical_rel,
            project_root=project_root,
            sticky_skill_ids=sticky_skill_ids,
        )
        evidence_md = evidence_cards_to_markdown(evidence_cards)
        literature_context = "\n\n".join(
            p for p in (evidence_md, str(lit_payload.get("text") or "")) if p.strip()
        )
        patch = parse_plot_edit_instruction(
            instruction=instruction,
            plot_type=plot_type,
            color_keys=color_keys,
            current_config=current,
            model=model,
            metadata_columns=metadata_columns,
            literature_context=literature_context or None,
        )
        from web_frontend.backend.plot_theme import merge_plot_config, sanitize_volcano_plot_patch

        soft_patch, soft_warn = suggest_soft_style_patch(
            plot_type,
            evidence_cards,
            metadata_columns=metadata_columns,
        )
        if plot_type == "volcano":
            soft_patch = sanitize_volcano_plot_patch(soft_patch)
        if soft_patch:
            patch = merge_plot_config(current, {**soft_patch, **patch})
        visual_warnings: list[str] = list(soft_warn)

        validation = validate_plot_patch(
            patch=patch,
            current_config=current,
            color_keys=color_keys,
            metadata_columns=metadata_columns,
            evidence_cards=evidence_cards,
            user_instruction=instruction,
            plot_type=plot_type,
        )
        if validation.get("errors"):
            raise PlotEditError("；".join(validation["errors"]))
        accepted_patch = validation.get("accepted_patch") or patch
        visual_warnings.extend(list(validation.get("warnings") or []))

        out_name = filename or stable_intent_filename(base or type_stem or source.stem)
        result = apply_plot_config(
            project_root=project_root,
            session_id=session_id,
            storage_slug=storage_slug,
            source_rel=canonical_rel,
            plot_config_patch=accepted_patch,
            instruction=instruction,
            filename=out_name,
            overwrite_intent=True,
        )
        result["agent_patch"] = accepted_patch
        result["edit_mode"] = "semantic"
        result["visual_ir"] = figure_ir
        result["evidence_refs"] = figure_ir.get("evidence_refs") or []
        result["visual_warnings"] = visual_warnings
        if lit_payload.get("matched"):
            result["literature_skills"] = lit_payload.get("matched")
            result["literature_hints"] = lit_payload.get("hints") or []
        after_cfg = (result.get("plot_config") or {}).get("data") or {}
        journal_path = append_journal_event(
            output_root=output_root,
            subdir="edited_plots",
            event_type="plot_edit",
            before=current,
            after=after_cfg if isinstance(after_cfg, dict) else {},
            user_instruction=instruction,
            evidence_refs=result["evidence_refs"],
            validation={"warnings": visual_warnings},
            output_files=[(result.get("file") or {}).get("name")],
        )
        result["journal"] = str(journal_path.relative_to(output_root))
        return result

    # 通用改图：任意结果 PNG（标题/字号/颜色）
    from web_frontend.backend.generic_plot_edit import (
        GenericPlotEditError,
        apply_generic_plot_edit,
    )

    try:
        result = apply_generic_plot_edit(
            project_root=project_root,
            storage_slug=storage_slug,
            source_rel=canonical_rel,
            instruction=instruction,
            model=model,
            filename=filename,
        )
    except GenericPlotEditError as exc:
        raise PlotEditError(str(exc)) from exc
    except ValueError as exc:
        raise PlotEditError(str(exc)) from exc
    return result


def resolve_chat_plot_edit_tasks(
    *,
    project_root: Path,
    storage_slug: str,
    message: str,
) -> tuple[list[tuple[str, str]], list[dict[str, Any]]]:
    output_root = session_work_dir(project_root, storage_slug).resolve()
    plots = list_editable_plots(output_root)
    tasks = extract_plot_edit_tasks(message, plots)
    if not tasks:
        raise PlotEditError(
            "未找到可 Agent 改图的图片。请先完成分析生成结果图，"
            "或在消息中指明图名/文件名（如 PCA、余弦分布、chemical_class_distribution.png）。"
        )
    return tasks, plots


def apply_analysis_intent_after_tool(
    *,
    project_root: Path,
    session_id: str,
    storage_slug: str,
    user_message: str,
    tool_name: str | None = None,
    output_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """任意出图工具成功后，按用户分析意图确定性重绘相关图（不依赖二次 LLM）。"""
    from web_frontend.backend.analysis_intent import (
        DEFAULT_COLORING_STEMS,
        default_stems_for_tool,
        describe_intent,
        has_analysis_plot_intent,
        parse_analysis_intent,
    )

    text = (user_message or "").strip()
    if not text or not has_analysis_plot_intent(text):
        return []

    upload_dir = session_upload_dir(project_root, storage_slug)
    try:
        metadata_csv = resolve_metadata_csv(upload_dir)
        metadata_columns = [str(c["name"]) for c in list_metadata_columns(metadata_csv)]
    except Exception:
        metadata_csv = None
        metadata_columns = []

    intent = parse_analysis_intent(
        text,
        metadata_columns=metadata_columns,
        metadata_csv=str(metadata_csv) if metadata_csv else None,
    )
    if not intent:
        return []

    # 缺列等硬错误：直接返回引导，不落盘半成品
    if intent.get("errors"):
        return [
            {
                "error": err,
                "stem": "color_by",
                "analysis_intent": describe_intent(intent),
            }
            for err in intent["errors"]
        ]

    # scores 类：再次确认 metadata 列（与 build 校验双保险）
    topology_keys = {"family", "degree", "chemical_category", "log2FC", "Cluster"}
    wanted = str(intent.get("color_by") or "").strip()
    if (
        not intent.get("cluster")
        and wanted
        and wanted not in topology_keys
        and metadata_columns
        and any(
            s in (intent.get("targets") or intent.get("target_stems") or DEFAULT_COLORING_STEMS)
            for s in ("pca_plot", "plsda_plot")
        )
    ):
        from web_frontend.backend.session_metadata import match_color_by_column

        matched = match_color_by_column(
            wanted,
            metadata_csv,
            columns=metadata_columns,
            fallback=False,
        )
        if not matched:
            available = ", ".join(metadata_columns)
            return [
                {
                    "error": (
                        f"metadata 中不存在「{wanted}」列，无法按该字段着色。"
                        f"可用列：{available}"
                    ),
                    "stem": "color_by",
                    "analysis_intent": describe_intent(intent),
                }
            ]
        intent["color_by"] = matched

    output_root = session_work_dir(project_root, storage_slug).resolve()
    search_roots: list[Path] = []
    if output_dir:
        search_roots.append(Path(output_dir))
    tool = tool_name or ""
    if "mixomics" in tool or tool == "statistical_analysis_mixomics":
        search_roots.extend(
            [output_root / "statistical_results", output_root / "mixomics_results"]
        )
    if "molecular_networking" in tool or "network" in tool:
        search_roots.append(output_root / "molecular_network_results")
    if "kegg" in tool:
        search_roots.append(output_root / "kegg_enrichment_results")
    if "ms2lda" in tool:
        search_roots.extend(
            [
                output_root / "ms2lda_results",
                output_root / "molecular_network_results" / "ms2lda",
            ]
        )
    search_roots.append(output_root)

    stems = (
        intent.get("targets")
        or intent.get("target_stems")
        or default_stems_for_tool(tool)
        or list(DEFAULT_COLORING_STEMS)
    )
    patch_keys = {
        "color_by",
        "color_type",
        "cluster",
        "thresholds",
        "color_channel",
        "marks",
        "facet",
        "size_by",
    }
    patch = {k: v for k, v in intent.items() if k in patch_keys and v is not None}

    results: list[dict[str, Any]] = []
    for stem in stems:
        # 按图类型裁剪 patch：PCA/PLS 才吃 color_by；火山才吃 thresholds
        stem_patch = dict(patch)
        if stem == "volcano_plot":
            for k in ("color_by", "color_type", "cluster", "facet", "size_by"):
                stem_patch.pop(k, None)
            # 显式只要火山 / 指定对比时：即使只有默认阈值也重绘，避免被 color_by 裁空后跳过
            if not stem_patch and (
                intent.get("thresholds")
                or intent.get("contrast")
                or stem in (intent.get("targets") or intent.get("target_stems") or [])
            ):
                thr = intent.get("thresholds") if isinstance(intent.get("thresholds"), dict) else {}
                stem_patch = {
                    "thresholds": {
                        "p": float(thr["p"]) if thr.get("p") is not None else 0.05,
                        "log2fc": float(thr["log2fc"]) if thr.get("log2fc") is not None else 1.0,
                    }
                }
        elif stem in ("pca_plot", "plsda_plot"):
            stem_patch.pop("thresholds", None)
            stem_patch.pop("color_channel", None)
        else:
            # 其它图族：保留通道/阈值，去掉 scores 专用字段
            if "color_by" in stem_patch and stem_patch.get("color_by") not in {
                "family",
                "degree",
                "chemical_category",
                "log2FC",
                "Cluster",
            }:
                # metadata 列着色主要对 scores 有意义
                pass
        if not stem_patch:
            continue

        rel_candidates: list[str] = []
        for root in search_roots:
            if not root.is_dir():
                continue
            png = root / f"{stem}.png"
            if png.is_file():
                try:
                    rel_candidates.append(png.relative_to(output_root).as_posix())
                    break
                except ValueError:
                    pass
            matches = list(root.rglob(f"{stem}.png"))
            matches = [p for p in matches if "edited_plots" not in p.parts]
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            for png in matches[:1]:
                try:
                    rel_candidates.append(png.relative_to(output_root).as_posix())
                    break
                except ValueError:
                    pass
            if rel_candidates:
                break
        for rel in rel_candidates:
            try:
                result = apply_plot_config(
                    project_root=project_root,
                    session_id=session_id,
                    storage_slug=storage_slug,
                    source_rel=rel,
                    plot_config_patch=stem_patch,
                    instruction=text,
                    filename=f"{stem}_intent.png",
                )
                result["edit_mode"] = "semantic"
                result["analysis_intent"] = describe_intent(intent)
                result["stem"] = stem
                if result.get("file", {}).get("name") and stem:
                    write_current_pointer(
                        output_root,
                        canonical_plot_base(stem) or stem,
                        result["file"]["name"],
                    )
                results.append(result)
            except Exception as exc:
                results.append({"error": str(exc), "source_rel": rel, "stem": stem})
    return results


def apply_analysis_coloring_after_stats(
    *,
    project_root: Path,
    session_id: str,
    storage_slug: str,
    user_message: str,
    statistical_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """兼容旧调用：统计后意图重绘。"""
    return apply_analysis_intent_after_tool(
        project_root=project_root,
        session_id=session_id,
        storage_slug=storage_slug,
        user_message=user_message,
        tool_name="statistical_analysis_mixomics",
        output_dir=statistical_dir,
    )
