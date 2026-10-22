"""改图终稿调用 web_frontend/backend/r_plots/render_edit.R。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

R_PLOT_TYPES = frozenset(
    {
        "pca",
        "plsda",
        "volcano",
        "vip_bar",
        "heatmap_vip",
        "kegg_bubble",
        "kegg_dotplot",
        "kegg_barplot",
    }
)

_SCRIPT = Path(__file__).resolve().parent / "r_plots" / "render_edit.R"


def find_rscript() -> str | None:
    env = (os.environ.get("MOA_RSCRIPT") or "").strip()
    candidates = [env] if env else []
    conda = (os.environ.get("CONDA_PREFIX") or "").strip()
    if conda:
        candidates.append(str(Path(conda) / "bin" / "Rscript"))
    candidates.append("/home/chenyihang/miniconda3/envs/MOA/bin/Rscript")
    found = shutil.which("Rscript")
    if found:
        candidates.append(found)
    for path in candidates:
        if path and Path(path).is_file():
            return path
    return None


def render_r_plot(spec: dict[str, Any]) -> Path:
    """按 spec 调 R。Rscript 不存在时抛 FileNotFoundError，脚本失败时抛 RuntimeError。"""
    rscript = find_rscript()
    if not rscript:
        raise FileNotFoundError("未找到 Rscript")
    if not _SCRIPT.is_file():
        raise FileNotFoundError(f"缺少 {_SCRIPT}")
    out = Path(str(spec["output_png"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="moa_rplot_") as tmp:
        spec_path = Path(tmp) / "spec.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        env = os.environ.copy()
        env["RGL_USE_NULL"] = "TRUE"
        proc = subprocess.run(
            [rscript, "--vanilla", str(_SCRIPT), str(spec_path)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    if proc.returncode != 0 or not out.is_file():
        tail = (proc.stderr or proc.stdout or "").strip()
        tail = tail[-1200:]
        raise RuntimeError(f"R 出图失败 ({spec.get('plot_type')}): {tail}")
    return out


def _opt_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _style_spec(plot_config: dict[str, Any]) -> dict[str, Any]:
    """各图共用的标题对齐、图例与字号，R 端 theme_moa 读取。"""
    legend = plot_config.get("legend") if isinstance(plot_config.get("legend"), dict) else {}
    out: dict[str, Any] = {
        "title_align": str(plot_config.get("title_align") or "left"),
        "legend_position": str(legend.get("position") or "right"),
        "legend_show": bool(legend.get("show", True)),
    }
    font = plot_config.get("font_size") if isinstance(plot_config.get("font_size"), dict) else {}
    sizes = {
        key: float(val)
        for key, val in font.items()
        if key in {"title", "axis", "legend", "label"} and isinstance(val, (int, float)) and val > 0
    }
    if sizes:
        out["font_size"] = sizes
    return out


def _ellipse_flag(plot_config: dict[str, Any]) -> bool:
    value = plot_config.get("ellipse")
    if isinstance(value, dict):
        return bool(value.get("show", True))
    if isinstance(value, bool):
        return value
    marks = plot_config.get("marks") if isinstance(plot_config.get("marks"), dict) else {}
    if isinstance(marks.get("ellipse"), bool):
        return bool(marks["ellipse"])
    return True


def render_score_r(
    *,
    output_path: str | Path,
    data_dir: str | Path | None,
    metadata_csv: str | Path | None,
    plot_config: dict[str, Any],
    plot_type: str,
) -> Path:
    root = Path(data_dir) if data_dir else Path(output_path).parent
    scores_name = "pca_scores.csv" if plot_type == "pca" else "plsda_scores.csv"
    from web_frontend.backend.plot_edit_registry import resolve_plot_data_file

    scores = resolve_plot_data_file(root, scores_name)
    if scores is None and root.name == "figures":
        scores = resolve_plot_data_file(root.parent.parent, scores_name)
    if scores is None:
        raise FileNotFoundError(f"缺少 {scores_name}")
    style = str(plot_config.get("score_style") or "simca")
    return render_r_plot(
        {
            "plot_type": plot_type,
            "output_png": str(output_path),
            "scores_csv": str(scores),
            "metadata_csv": _opt_str(metadata_csv),
            "title": str(plot_config.get("title") or ""),
            "score_style": style,
            "color_by": str(plot_config.get("color_by") or "Group"),
            "size_by": _opt_str(plot_config.get("size_by")),
            "components": list(plot_config.get("components") or [1, 2]),
            "show_labels": bool(plot_config.get("show_sample_labels", True)),
            "palette": dict(plot_config.get("palette") or {}),
            "ellipse": _ellipse_flag(plot_config),
            "edit_kind": str(plot_config.get("edit_kind") or "style"),
            **_style_spec(plot_config),
        }
    )


def render_volcano_r(volcano_csv: str | Path, plot_config: dict[str, Any], output_path: str | Path) -> Path:
    from web_frontend.backend.plot_theme import resolve_volcano_thresholds

    thresholds = resolve_volcano_thresholds(plot_config)
    explicit = plot_config.get("thresholds") if isinstance(plot_config.get("thresholds"), dict) else {}
    p_stat = str(plot_config.get("p_stat") or "")
    if p_stat == "padj" and explicit.get("padj") is not None:
        p_cut = float(explicit["padj"])
    elif explicit.get("p") is not None:
        p_stat = "pvalue"
        p_cut = float(explicit["p"])
    else:
        p_stat = "pvalue"
        p_cut = thresholds.get("p")
    colors = dict(plot_config.get("colors") or {})
    return render_r_plot(
        {
            "plot_type": "volcano",
            "output_png": str(output_path),
            "volcano_csv": str(volcano_csv),
            "title": str(plot_config.get("title") or ""),
            "p_cut": p_cut,
            "fc_cut": thresholds.get("log2fc"),
            "p_stat": p_stat or "pvalue",
            "edit_kind": str(plot_config.get("edit_kind") or "style"),
            "colors": colors,
            **_style_spec(plot_config),
        }
    )


def render_vip_bar_r(data_dir: str | Path, plot_config: dict[str, Any], output_path: str | Path) -> Path:
    from web_frontend.backend.paper_plot_helpers import vip_threshold_from_config
    from web_frontend.backend.plot_edit_registry import resolve_plot_data_file

    root = Path(data_dir)
    vip = resolve_plot_data_file(root, "vip_scores.csv")
    if vip is None:
        raise FileNotFoundError("缺少 vip_scores.csv")
    volcano = resolve_plot_data_file(root, "volcano_results.csv")
    marks = plot_config.get("marks") if isinstance(plot_config.get("marks"), dict) else {}
    edit_kind = str(plot_config.get("edit_kind") or "style")
    explicit_vip = plot_config.get("vip_threshold")
    if not isinstance(explicit_vip, (int, float)):
        explicit_vip = marks.get("vip_threshold") if isinstance(marks.get("vip_threshold"), (int, float)) else None
    return render_r_plot(
        {
            "plot_type": "vip_bar",
            "output_png": str(output_path),
            "vip_csv": str(vip),
            "volcano_csv": str(volcano) if volcano else "",
            "title": str(plot_config.get("title") or ""),
            "vip_threshold": float(explicit_vip) if explicit_vip is not None else vip_threshold_from_config(plot_config),
            "top_n": int(marks.get("top_n") or 30),
            "colors": dict(plot_config.get("colors") or {}),
            "edit_kind": edit_kind,
            "apply_filter": explicit_vip is not None,
            **_style_spec(plot_config),
        }
    )


def render_heatmap_r(
    data_dir: str | Path,
    plot_config: dict[str, Any],
    output_path: str | Path,
    metadata_csv: str | Path | None,
) -> Path:
    from web_frontend.backend.paper_plot_helpers import DEFAULT_HEATMAP_MAX_ROWS
    from web_frontend.backend.plot_edit_registry import resolve_plot_data_file

    matrix = resolve_plot_data_file(Path(data_dir), "heatmap_top_vip_matrix.csv")
    if matrix is None:
        raise FileNotFoundError("缺少 heatmap_top_vip_matrix.csv")
    marks = plot_config.get("marks") if isinstance(plot_config.get("marks"), dict) else {}
    edit_kind = str(plot_config.get("edit_kind") or "style")
    vip = resolve_plot_data_file(Path(data_dir), "vip_scores.csv")
    return render_r_plot(
        {
            "plot_type": "heatmap_vip",
            "output_png": str(output_path),
            "matrix_csv": str(matrix),
            "vip_csv": str(vip) if vip else "",
            "metadata_csv": _opt_str(metadata_csv),
            "title": str(plot_config.get("title") or ""),
            "max_rows": int(marks.get("top_n") or DEFAULT_HEATMAP_MAX_ROWS),
            "cmap": str(plot_config.get("cmap") or ""),
            "colors": dict(plot_config.get("colors") or {}),
            "vip_threshold": plot_config.get("vip_threshold"),
            "edit_kind": edit_kind,
            "apply_filter": isinstance(plot_config.get("vip_threshold"), (int, float)),
            **_style_spec(plot_config),
        }
    )


def render_kegg_r(data_dir: str | Path, plot_config: dict[str, Any], output_path: str | Path, plot_type: str) -> Path:
    from web_frontend.backend.plot_edit_registry import resolve_plot_data_file

    table = resolve_plot_data_file(Path(data_dir), "kegg_compound_enrich.csv")
    if table is None:
        raise FileNotFoundError("缺少 kegg_compound_enrich.csv")
    marks = plot_config.get("marks") if isinstance(plot_config.get("marks"), dict) else {}
    edit_kind = str(plot_config.get("edit_kind") or "style")
    fdr_cut = plot_config.get("fdr_cut")
    return render_r_plot(
        {
            "plot_type": plot_type,
            "output_png": str(output_path),
            "kegg_csv": str(table),
            "title": str(plot_config.get("title") or ""),
            "top_n": int(marks.get("top_n") or 15),
            "fdr_cut": fdr_cut,
            "colors": dict(plot_config.get("colors") or {}),
            "edit_kind": edit_kind,
            "apply_filter": isinstance(fdr_cut, (int, float)),
            **_style_spec(plot_config),
        }
    )
