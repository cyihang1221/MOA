"""Web 端 Agent 改图服务：解析意图 → 合并 plot_config → matplotlib 重绘。"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from src.platform_utils import normalize_display_path

from web_frontend.backend.plot_edit_agent import parse_plot_edit_instruction
from web_frontend.backend.plot_edit_registry import (
    extract_plot_edit_tasks,
    get_plot_spec,
    is_agent_plot_editable_stem,
    list_editable_plots,
    plot_data_files_ready,
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
from web_frontend.backend.plot_theme import (
    merge_plot_config,
    normalize_plot_config,
    plot_config_path_for_png,
)
from web_frontend.backend.session_metadata import resolve_metadata_csv
from web_frontend.backend.session_storage import edited_plots_dir, session_upload_dir, session_work_dir
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
) -> list[Path]:
    """为可语义编辑的 PNG 补写 plot_config / Vega-Lite / SVG sidecar。"""
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

    for png in sorted(root.glob("*.png")):
        stem = png.stem
        if not is_agent_plot_editable_stem(stem):
            continue
        plot_type = plot_type_from_stem(stem)
        if not plot_type:
            continue
        spec = get_plot_spec(plot_type)
        if not spec:
            continue
        if not plot_data_files_ready(root, spec.data_files):
            continue

        config_path = Path(plot_config_path_for_png(str(png)))
        color_keys: list[str] = []
        try:
            if upload is not None:
                color_keys = _color_keys_for_plot(plot_type, root, upload)
            elif plot_type == "volcano":
                color_keys = ["significant", "nonsignificant"]
            elif plot_type == "family_size":
                nodes = resolve_plot_data_file(root, "network_nodes.csv")
                labels, _, _ = _family_size_payload(nodes) if nodes else ([], [], [])
                color_keys = labels
            elif plot_type in ("degree_hist", "cosine_hist", "precursor_mass_diff"):
                color_keys = ["histogram_color", "threshold_color", "median_color"]
            elif plot_type == "vip_bar":
                color_keys = ["bar_color"]
            elif plot_type == "network_topology":
                layout = pd.read_csv(root / "network_layout.csv")
                if "family" in layout.columns:
                    color_keys = list(dict.fromkeys(str(v) for v in layout["family"].fillna("singleton")))
        except Exception:
            color_keys = []

        existing = None
        if config_path.is_file():
            try:
                existing = json.loads(config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = None
        config = normalize_plot_config(existing if isinstance(existing, dict) else None, plot_type=plot_type, color_keys=color_keys)
        config["source_rel"] = png.name
        try:
            vega_spec = build_vegalite_spec(
                plot_type=plot_type,
                data_dir=root,
                metadata_csv=metadata_csv if plot_type in {"pca", "plsda"} else None,
                plot_config=config,
            )
        except Exception:
            # 数据不齐时至少写 plot_config，便于前端打开后再报错
            if not config_path.is_file():
                config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
                written.append(config_path)
            continue

        write_semantic_metadata_files(
            png_path=png,
            plot_config=config,
            vega_spec=vega_spec,
            source_rel=png.name,
        )
        write_svg_sidecar(vega_spec, png)
        written.append(config_path)

    # vip_scores.csv 存在但无 PNG 时，生成可 SVG 编辑的 VIP 柱状图
    vip_csv = root / "vip_scores.csv"
    vip_png = root / "vip_scores.png"
    if vip_csv.is_file() and not vip_png.is_file():
        try:
            config = normalize_plot_config(None, plot_type="vip_bar", color_keys=["bar_color"])
            config["source_rel"] = vip_png.name
            vega_spec = build_vegalite_spec(
                plot_type="vip_bar",
                data_dir=root,
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


def _resolve_output_png(output_root: Path, source: Path, filename: str | None) -> Path:
    edit_dir = edited_plots_dir(output_root)
    stem = Path(filename or f"{source.stem}_edited.png").stem
    target = edit_dir / f"{stem}.png"
    if target.exists():
        target = edit_dir / f"{stem}_{uuid.uuid4().hex[:8]}.png"
    return target


def _validated_source(
    output_root: Path,
    source_rel: str,
    *,
    hint_message: str | None = None,
) -> Path:
    try:
        canonical = resolve_plot_source_rel(
            output_root,
            source_rel,
            hint_message=hint_message,
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
    color_keys = _color_keys_for_plot(plot_type, data_dir, upload_dir)
    config = normalize_plot_config(existing, plot_type=plot_type, color_keys=color_keys)
    if plot_config_patch:
        config = normalize_plot_config(
            merge_plot_config(config, plot_config_patch),
            plot_type=plot_type,
            color_keys=color_keys,
        )
    metadata_csv = resolve_metadata_csv(upload_dir) if plot_type in {"pca", "plsda"} else None
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
    }


def _color_keys_for_plot(plot_type: str, data_dir: Path, upload_dir: Path) -> list[str]:
    if plot_type in ("pca", "plsda"):
        spec = get_plot_spec(plot_type)
        if not spec:
            return []
        scores_path = data_dir / spec.data_files[0]
        metadata_csv = resolve_metadata_csv(upload_dir)
        _, groups, _, _ = load_scores_and_groups(scores_path, metadata_csv)
        seen: set[str] = set()
        ordered: list[str] = []
        for g in groups:
            gs = str(g)
            if gs not in seen:
                seen.add(gs)
                ordered.append(gs)
        return ordered
    if plot_type == "volcano":
        return ["significant", "nonsignificant"]
    if plot_type == "family_size":
        nodes = resolve_plot_data_file(data_dir, "network_nodes.csv")
        if nodes is None:
            return []
        labels, _, _ = _family_size_payload(nodes)
        return labels
    if plot_type in ("degree_hist", "cosine_hist", "precursor_mass_diff"):
        return ["histogram_color", "threshold_color", "median_color"]
    if plot_type == "vip_bar":
        return ["bar_color"]
    if plot_type == "network_topology":
        layout = data_dir / "network_layout.csv"
        if layout.is_file():
            frame = pd.read_csv(layout)
            if "family" in frame.columns:
                return list(dict.fromkeys(str(v) for v in frame["family"].fillna("singleton")))
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
        scores, groups, samples, axis_names = load_scores_and_groups(scores_path, metadata_csv)
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
        volcano_csv = data_dir / spec.data_files[0]
        render_volcano_plot_png(volcano_csv, plot_config, output_path)
        return build_echarts_volcano(volcano_csv, plot_config)

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

    # vip / heatmap / topology：matplotlib 回退缺失时复制原图
    if plot_type in {"vip_bar", "heatmap_vip", "network_topology"}:
        import shutil

        source_name = spec.stem_prefix + ".png"
        source_png = data_dir / source_name
        if source_png.is_file() and source_png.resolve() != output_path.resolve():
            shutil.copy2(source_png, output_path)
        elif not output_path.is_file():
            raise PlotEditError(f"缺少 vl-convert 且无法回退渲染: {plot_type}")
        return {}

    raise PlotEditError(f"暂不支持重绘: {plot_type}")


def apply_plot_config(
    *,
    project_root: Path,
    session_id: str,
    storage_slug: str,
    source_rel: str,
    plot_config_patch: dict[str, Any],
    instruction: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    output_root = session_work_dir(project_root, storage_slug).resolve()
    canonical_rel = resolve_plot_source_rel(output_root, source_rel, hint_message=instruction)
    initial_source = _validated_source(output_root, canonical_rel, hint_message=instruction)
    base_existing = _load_existing_config(initial_source)
    source, data_dir = _resolve_source_and_data_dir(output_root, canonical_rel, base_existing)

    stem = source.stem
    existing_plot_type = str((base_existing or {}).get("plot_type") or "")
    plot_type = plot_type_from_stem(stem) or existing_plot_type
    # 语义重绘仅服务于有 PlotSpec 的图；其余应走 agent_apply → generic
    if not get_plot_spec(plot_type or ""):
        raise PlotEditError(
            f"暂不支持语义重绘：{source.name}。"
            "请使用 Agent 通用改图（标题/字号/颜色）。"
        )

    upload_dir = session_upload_dir(project_root, storage_slug)
    color_keys = _color_keys_for_plot(plot_type, data_dir, upload_dir)

    base = normalize_plot_config(base_existing, plot_type=plot_type, color_keys=color_keys)
    merged = merge_plot_config(base, plot_config_patch)
    merged = normalize_plot_config(merged, plot_type=plot_type, color_keys=color_keys)

    target_png = _resolve_output_png(output_root, source, filename)
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

    config_path, vega_path, svg_path, _ = write_semantic_outputs(
        png_path=target_png,
        plot_config=merged,
        vega_spec=vega_spec,
        instruction=instruction,
        source_rel=str((base_existing or {}).get("source_rel") or canonical_rel),
        png_renderer=_render_png_fallback,
    )

    stat = target_png.stat()
    rel_png = target_png.relative_to(output_root).as_posix()
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
        "source_rel": canonical_rel,
        "plot_type": plot_type,
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

    source = _validated_source(output_root, canonical_rel, hint_message=instruction)
    existing = _load_existing_config(source)
    plot_type = plot_type_from_stem(source.stem) or str((existing or {}).get("plot_type") or "")
    upload_dir = session_upload_dir(project_root, storage_slug)
    _, data_dir = _resolve_source_and_data_dir(output_root, canonical_rel, existing)

    # 语义改图：有 PlotSpec 且数据齐全
    spec = get_plot_spec(plot_type) if plot_type else None
    can_semantic = bool(spec and plot_data_files_ready(data_dir, spec.data_files))
    if can_semantic:
        color_keys = _color_keys_for_plot(plot_type, data_dir, upload_dir)
        current = normalize_plot_config(existing, plot_type=plot_type, color_keys=color_keys)
        patch = parse_plot_edit_instruction(
            instruction=instruction,
            plot_type=plot_type,
            color_keys=color_keys,
            current_config=current,
            model=model,
        )
        result = apply_plot_config(
            project_root=project_root,
            session_id=session_id,
            storage_slug=storage_slug,
            source_rel=canonical_rel,
            plot_config_patch=patch,
            instruction=instruction,
            filename=filename,
        )
        result["agent_patch"] = patch
        result["edit_mode"] = "semantic"
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
