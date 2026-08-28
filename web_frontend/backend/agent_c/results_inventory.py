"""清点 Agent B 的结果目录，标出可出图的数据文件。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from web_frontend.backend.agent_c.contract import CONTRACT_VERSION, STANDARD_RESULT_FILES
from web_frontend.backend.plot_edit_registry import (
    PLOT_SPECS,
    plot_data_files_ready,
    resolve_plot_data_file,
)

_SKIP_DIRS = {
    "edited_plots",
    "merged_figures",
    "agent_c_output",
    "__pycache__",
    ".git",
}


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def find_metadata_csv(results_dir: Path, extra: str | Path | None = None) -> Path | None:
    if extra:
        p = Path(extra)
        if p.is_file():
            return p
    for name in ("metadata.csv", "sample_metadata.csv"):
        direct = results_dir / name
        if direct.is_file():
            return direct
        parent = results_dir.parent / name
        if parent.is_file():
            return parent
    for hit in results_dir.rglob("metadata.csv"):
        if hit.is_file() and hit.parent.name not in _SKIP_DIRS:
            return hit
    return None


def inventory_results(
    results_dir: str | Path,
    *,
    metadata_csv: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(results_dir)
    manifest: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "results_dir": str(root.resolve()) if root.exists() else str(root),
        "exists": root.is_dir(),
        "files": [],
        "plottable": [],
        "standard_files": {},
        "metadata_csv": None,
        "result_summary": "",
        "warnings": [],
    }
    if not root.is_dir():
        manifest["warnings"].append(f"结果目录不存在: {root}")
        return manifest

    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        files.append(
            {
                "rel": _rel(root, path),
                "name": path.name,
                "suffix": path.suffix.lower(),
                "size": path.stat().st_size,
            }
        )
    manifest["files"] = files

    names = {f["name"] for f in files}
    for logical, aliases in STANDARD_RESULT_FILES.items():
        hit = next((a for a in aliases if a in names), None)
        manifest["standard_files"][logical] = hit

    summary_path = None
    for cand in (root / "result_summary.md", root / "result_summary.txt"):
        if cand.is_file():
            summary_path = cand
            break
    if summary_path:
        try:
            manifest["result_summary"] = summary_path.read_text(encoding="utf-8")[:8000]
        except OSError:
            pass

    meta = find_metadata_csv(root, metadata_csv)
    manifest["metadata_csv"] = str(meta) if meta else None

    plottable: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    dirs = {root}
    for path in root.rglob("*"):
        if path.is_dir() and path.name not in _SKIP_DIRS:
            dirs.add(path)
    for data_dir in sorted(dirs, key=lambda p: len(p.parts)):
        for spec in PLOT_SPECS:
            if not plot_data_files_ready(data_dir, spec.data_files):
                continue
            key = (spec.plot_type, str(data_dir))
            if key in seen:
                continue
            seen.add(key)
            resolved = {
                name: str(resolve_plot_data_file(data_dir, name) or "")
                for name in spec.data_files
            }
            existing_png = data_dir / f"{spec.stem_prefix}.png"
            plottable.append(
                {
                    "plot_type": spec.plot_type,
                    "stem": spec.stem_prefix,
                    "title": spec.default_title,
                    "data_dir": str(data_dir),
                    "data_files": resolved,
                    "existing_png": str(existing_png) if existing_png.is_file() else None,
                }
            )
    manifest["plottable"] = plottable
    if not plottable:
        manifest["warnings"].append("未找到可渲染的语义数据文件（如 pca_scores.csv / volcano_results.csv）")
    return manifest
