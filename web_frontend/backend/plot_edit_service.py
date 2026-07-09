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
    plot_type_from_stem,
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


class PlotEditError(Exception):
    pass


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
        labels, _, _ = _family_size_payload(data_dir / "network_nodes.csv")
        return labels
    if plot_type in ("degree_hist", "cosine_hist"):
        return ["histogram_color", "threshold_color", "median_color"]
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
        nodes_csv = data_dir / spec.data_files[0]
        labels, sizes, colors = _family_size_payload(nodes_csv)
        palette = plot_config.get("palette") or {}
        for i, label in enumerate(labels):
            if label in palette:
                colors[i] = palette[label]
        render_family_size_png(nodes_csv, plot_config, output_path)
        return build_echarts_bar(labels, sizes, colors, plot_config)

    if plot_type == "degree_hist":
        nodes_csv = data_dir / spec.data_files[0]
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
        edges_csv = data_dir / spec.data_files[0]
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
    source = (output_root / source_rel.strip().lstrip("/")).resolve()
    try:
        source.relative_to(output_root)
    except ValueError as exc:
        raise PlotEditError("只能编辑 outputspace 中的图片") from exc
    if not source.is_file() or source.suffix.lower() != ".png":
        raise PlotEditError("source_rel 必须是 output 目录下的 PNG 文件")

    stem = source.stem
    if not is_agent_plot_editable_stem(stem):
        raise PlotEditError(f"暂不支持 Agent 重绘该图：{source.name}")

    plot_type = plot_type_from_stem(stem)
    if plot_type is None:
        raise PlotEditError(f"无法识别图类型：{source.name}")

    upload_dir = session_upload_dir(project_root, storage_slug)
    data_dir = source.parent
    color_keys = _color_keys_for_plot(plot_type, data_dir, upload_dir)

    base_existing = _load_existing_config(source)
    base = normalize_plot_config(base_existing, plot_type=plot_type, color_keys=color_keys)
    merged = merge_plot_config(base, plot_config_patch)
    merged = normalize_plot_config(merged, plot_type=plot_type, color_keys=color_keys)

    target_png = _resolve_output_png(output_root, source, filename)
    echarts_option = _render_and_build_echarts(
        plot_type=plot_type,
        data_dir=data_dir,
        upload_dir=upload_dir,
        plot_config=merged,
        output_path=target_png,
    )
    config_path, echarts_path = save_plot_sidecars(
        png_path=target_png,
        plot_config=merged,
        echarts_option=echarts_option,
        instruction=instruction,
        source_rel=source_rel,
    )

    stat = target_png.stat()
    rel_png = target_png.relative_to(output_root).as_posix()
    return {
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
        "echarts": {
            "name": echarts_path.relative_to(output_root).as_posix(),
            "path": normalize_display_path(echarts_path),
        },
        "source_rel": source_rel,
        "plot_type": plot_type,
    }


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
    source = (output_root / source_rel.strip().lstrip("/")).resolve()
    plot_type = plot_type_from_stem(source.stem)
    if plot_type is None:
        raise PlotEditError(f"暂不支持 Agent 改图：{source.name}")

    upload_dir = session_upload_dir(project_root, storage_slug)
    color_keys = _color_keys_for_plot(plot_type, source.parent, upload_dir)
    existing = _load_existing_config(source)
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
        source_rel=source_rel,
        plot_config_patch=patch,
        instruction=instruction,
        filename=filename,
    )
    result["agent_patch"] = patch
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
            "未找到可 Agent 重绘的图。请先完成统计分析或分子网络分析，"
            "或在消息中指明图名（如 PCA、火山图、余弦分布）。"
        )
    return tasks, plots
