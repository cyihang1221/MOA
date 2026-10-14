"""论文逻辑文件名 ↔ Agent B 目录的硬契约。

C 只消费文件、不跑 XCMS。本表规定：
- 默认 LC-MS 会话：mixOmics/结果/pca_scores.csv ↔ 逻辑名 pca_scores.csv
- 论文专用名（volatile_pca_scores.csv、tea_constituents.csv）不得用 mixOmics 得分表冒充
- 缺文件标缺，不画错图

Skill 参数进 B 见 ``agent_b/skill_param_inject.py``（写 tool_parameters）。
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from web_frontend.backend.plot_data_contract import PAPER_ONLY_FILES

CONTRACT_DIR_NAME = "_b_contract"
FILE_MAP_NAME = "b_file_map.json"
RESULTS_LEAF = "结果"

_SKIP_DIRS = {
    "edited_plots",
    "merged_figures",
    "agent_c_output",
    "_abc_handoff",
    "_handoff_input",
    CONTRACT_DIR_NAME,
    "__pycache__",
    ".git",
}

# 论文/GC-MS/湿实验表：只认同名文件，禁止挂到 mixOmics PCA/VIP。
PAPER_STRICT_FILES: frozenset[str] = PAPER_ONLY_FILES | frozenset(
    {
        "volatile_pca_scores.csv",
        "volatile_plsda_scores.csv",
        "volatile_network_nodes.csv",
        "volatile_network_edges.csv",
        "volatile_network_layout.csv",
    }
)


@dataclass(frozen=True)
class FileBinding:
    logical_name: str
    b_rel_globs: tuple[str, ...]
    also_basenames: tuple[str, ...] = ()
    never_from: tuple[str, ...] = ()
    source: str = "b_tool"
    producer_tools: tuple[str, ...] = ()
    notes: str = ""


def _mixomics(*names: str) -> tuple[str, ...]:
    out: list[str] = []
    for name in names:
        out.extend(
            (
                f"mixOmics/{RESULTS_LEAF}/{name}",
                f"mixomics/{RESULTS_LEAF}/{name}",
                f"statistical_analysis_mixomics/{name}",
                f"**/{name}",
            )
        )
    return tuple(out)


_CORE_BINDINGS: tuple[FileBinding, ...] = (
    FileBinding(
        "pca_scores.csv",
        _mixomics("pca_scores.csv"),
        also_basenames=("statistical_analysis_metax_pca_scores.csv",),
        never_from=("volatile_pca_scores.csv",),
        producer_tools=("mixOmics", "metaX"),
        notes="默认 LC-MS 非靶向 PCA",
    ),
    FileBinding(
        "plsda_scores.csv",
        _mixomics("plsda_scores.csv"),
        never_from=("volatile_plsda_scores.csv",),
        producer_tools=("mixOmics",),
    ),
    FileBinding(
        "vip_scores.csv",
        _mixomics("vip_scores.csv"),
        also_basenames=(
            "statistical_analysis_metaboanalyst_vip.csv",
            "statistical_analysis_simca_result.csv",
        ),
        producer_tools=("mixOmics", "SIMCA", "MetaboAnalyst"),
    ),
    FileBinding(
        "volcano_results.csv",
        _mixomics("volcano_results.csv"),
        also_basenames=(
            "statistical_analysis_metax_result.csv",
            "statistical_analysis_sklearn_result.csv",
            "statistical_analysis_metaboanalyst_result.csv",
            "statistical_analysis_simca_result.csv",
        ),
        producer_tools=("mixOmics", "metaX", "SIMCA"),
    ),
    FileBinding(
        "heatmap_top_vip_matrix.csv",
        _mixomics("heatmap_top_vip_matrix.csv"),
        producer_tools=("mixOmics",),
    ),
    FileBinding(
        "plsda_permutation.csv",
        (
            f"mixOmics/{RESULTS_LEAF}/plsda_permutation.csv",
            f"SIMCA/{RESULTS_LEAF}/plsda_permutation.csv",
            f"SIMCA/{RESULTS_LEAF}/statistical_analysis_simca_permutation.csv",
            "**/plsda_permutation.csv",
            "**/statistical_analysis_simca_permutation.csv",
        ),
        also_basenames=("statistical_analysis_simca_permutation.csv",),
        never_from=("pca_scores.csv", "vip_scores.csv", "heatmap_top_vip_matrix.csv"),
        source="mixed",
        producer_tools=("SIMCA", "mixOmics"),
        notes="mixOmics 默认不写置换表；缺则标缺，不用得分表冒充",
    ),
    FileBinding(
        "network_nodes.csv",
        (
            f"FBMN/{RESULTS_LEAF}/network_nodes.csv",
            f"FBMN/{RESULTS_LEAF}/fbmn_nodes.csv",
            f"GNPS/{RESULTS_LEAF}/network_nodes.csv",
            "**/network_nodes.csv",
            "**/fbmn_nodes.csv",
            "**/enhanced_nodes.csv",
        ),
        also_basenames=("fbmn_nodes.csv", "enhanced_nodes.csv"),
        never_from=("volatile_network_nodes.csv",),
        producer_tools=("FBMN", "GNPS", "MolNetEnhancer"),
    ),
    FileBinding(
        "network_edges.csv",
        (
            f"FBMN/{RESULTS_LEAF}/network_edges.csv",
            f"FBMN/{RESULTS_LEAF}/fbmn_edges.csv",
            "**/network_edges.csv",
            "**/fbmn_edges.csv",
        ),
        also_basenames=("fbmn_edges.csv",),
        never_from=("volatile_network_edges.csv",),
        producer_tools=("FBMN", "GNPS"),
    ),
    FileBinding(
        "network_layout.csv",
        (
            "**/network_layout.csv",
            f"FBMN/{RESULTS_LEAF}/network_nodes.csv",
            "**/fbmn_nodes.csv",
        ),
        also_basenames=("network_nodes.csv", "fbmn_nodes.csv", "enhanced_nodes.csv"),
        producer_tools=("FBMN",),
        source="derived",
        notes="B 常不写 layout，C 从节点表派生",
    ),
    FileBinding(
        "feature_table.csv",
        (
            f"XCMS-Centwave/{RESULTS_LEAF}/feature_table.csv",
            f"MZMine-Pipeline/{RESULTS_LEAF}/feature_table.csv",
            "**/feature_table.csv",
        ),
        producer_tools=("XCMS-Centwave", "MZMine-Pipeline"),
    ),
    FileBinding(
        "feature_table_filtered_imputed.csv",
        (
            f"kNN/{RESULTS_LEAF}/feature_table_filtered_imputed.csv",
            "**/feature_table_filtered_imputed.csv",
        ),
        also_basenames=("feature_table_filtered.csv",),
        producer_tools=("kNN",),
    ),
    FileBinding(
        "kegg_compound_enrich.csv",
        (f"KEGG/{RESULTS_LEAF}/kegg_compound_enrich.csv", "**/kegg_compound_enrich.csv"),
        producer_tools=("KEGG",),
    ),
)

_PAPER_BINDINGS = tuple(
    FileBinding(
        paper_name,
        (paper_name, f"**/{paper_name}"),
        also_basenames=(),
        never_from=(
            "pca_scores.csv",
            "plsda_scores.csv",
            "vip_scores.csv",
            "heatmap_top_vip_matrix.csv",
            "volcano_results.csv",
        ),
        source="paper_or_upload",
        producer_tools=(),
        notes="论文/上传专用；质谱默认流水线不会写此文件",
    )
    for paper_name in sorted(PAPER_STRICT_FILES)
)

FILE_BINDINGS: tuple[FileBinding, ...] = _CORE_BINDINGS + _PAPER_BINDINGS


def binding_by_name() -> dict[str, FileBinding]:
    return {item.logical_name: item for item in FILE_BINDINGS}


def is_paper_strict(filename: str) -> bool:
    return Path(str(filename or "")).name in PAPER_STRICT_FILES


def _skip_path(path: Path) -> bool:
    return any(part in _SKIP_DIRS for part in path.parts)


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _producer_from_path(rel: str) -> str:
    parts = Path(rel).parts
    if len(parts) >= 2 and parts[1] == RESULTS_LEAF:
        return parts[0]
    if parts:
        return parts[0]
    return ""


def _forbidden(binding: FileBinding, path: Path) -> bool:
    name = path.name
    if name in binding.never_from:
        return True
    if binding.logical_name in PAPER_STRICT_FILES and name != binding.logical_name:
        return True
    return False


def _iter_glob(root: Path, pattern: str) -> list[Path]:
    if not pattern:
        return []
    if "/" not in pattern and "**" not in pattern:
        direct = root / pattern
        return [direct] if direct.is_file() else []
    try:
        return [p for p in root.glob(pattern) if p.is_file() and not _skip_path(p)]
    except OSError:
        return []


def resolve_logical_file(results_dir: str | Path, logical_name: str) -> Path | None:
    """在 B 结果树中解析一个论文/C 逻辑文件名。找不到或只能靠禁用别名时返回 None。"""
    rec = resolve_logical_record(results_dir, logical_name)
    if rec and rec.get("status") == "present" and rec.get("path"):
        return Path(str(rec["path"]))
    return None


def resolve_logical_record(results_dir: str | Path, logical_name: str) -> dict[str, Any]:
    root = Path(results_dir)
    name = Path(str(logical_name or "")).name
    empty = {
        "logical_name": name,
        "status": "missing",
        "path": None,
        "rel": None,
        "producer": "",
        "alias_used": None,
        "source": "unknown",
        "notes": "未登记且未找到同名文件",
    }
    if not name:
        return empty
    table = binding_by_name()
    binding = table.get(name)
    if not root.is_dir():
        rec = dict(empty)
        rec["notes"] = f"结果目录不存在: {root}"
        rec["source"] = binding.source if binding else "unknown"
        return rec

    candidates: list[tuple[str, Path]] = []
    if binding:
        for pattern in binding.b_rel_globs:
            for hit in _iter_glob(root, pattern):
                if _forbidden(binding, hit):
                    continue
                candidates.append((hit.name, hit))
                if candidates:
                    break
            if candidates:
                break
        if not candidates:
            for alt in binding.also_basenames:
                if alt in binding.never_from or name in PAPER_STRICT_FILES:
                    continue
                for hit in root.rglob(alt):
                    if not hit.is_file() or _skip_path(hit) or _forbidden(binding, hit):
                        continue
                    candidates.append((alt, hit))
                    break
                if candidates:
                    break
    else:
        exact = root / name
        if exact.is_file():
            candidates.append((name, exact))
        else:
            for hit in root.rglob(name):
                if hit.is_file() and not _skip_path(hit):
                    candidates.append((name, hit))
                    break

    if not candidates:
        rec = dict(empty)
        rec["source"] = binding.source if binding else "unknown"
        rec["notes"] = (binding.notes if binding else "") or "未找到对应 B 产物"
        if name in PAPER_STRICT_FILES:
            rec["notes"] = (
                f"缺 `{name}`：这是论文/上传文件，不能用 mixOmics/结果/pca_scores.csv 替代"
            )
        elif name == "plsda_permutation.csv":
            rec["notes"] = (
                "缺 `plsda_permutation.csv`：mixOmics 默认不写置换表；"
                "若未跑 SIMCA 且未上传该表，标缺"
            )
        return rec

    alias, path = candidates[0]
    rel = _rel(root, path)
    return {
        "logical_name": name,
        "status": "present",
        "path": str(path.resolve()),
        "rel": rel,
        "producer": _producer_from_path(rel),
        "alias_used": None if alias == name else alias,
        "source": binding.source if binding else "exact",
        "notes": binding.notes if binding else "",
    }


def build_file_map(
    results_dir: str | Path,
    extra_names: Iterable[str] | None = None,
) -> dict[str, dict[str, Any]]:
    names = [item.logical_name for item in FILE_BINDINGS]
    for extra in extra_names or []:
        base = Path(str(extra)).name
        if base and base not in names:
            names.append(base)
    return {name: resolve_logical_record(results_dir, name) for name in names}


def materialize_logical_view(
    results_dir: str | Path,
    file_map: dict[str, dict[str, Any]] | None = None,
    *,
    dest_name: str = CONTRACT_DIR_NAME,
) -> dict[str, Any]:
    """把已解析文件落到 ``_b_contract/<逻辑名>``，供 C 用论文文件名读取。"""
    root = Path(results_dir)
    dest = root / dest_name
    mapping = file_map or build_file_map(root)
    dest.mkdir(parents=True, exist_ok=True)
    known = set(binding_by_name())
    written: list[str] = []
    skipped: list[str] = []
    for name, rec in mapping.items():
        if name not in known:
            skipped.append(name)
            continue
        if rec.get("status") != "present" or not rec.get("path"):
            skipped.append(name)
            continue
        src = Path(str(rec["path"]))
        if not src.is_file():
            skipped.append(name)
            continue
        target = dest / name
        if target.is_file() or target.is_symlink():
            try:
                target.unlink()
            except OSError:
                pass
        try:
            os.link(src, target)
        except OSError:
            try:
                shutil.copy2(src, target)
            except OSError:
                skipped.append(name)
                continue
        written.append(name)
        rec["contract_rel"] = f"{dest_name}/{name}"
    return {
        "contract_dir": str(dest),
        "n_linked": len(written),
        "linked": written,
        "missing": skipped,
    }


def dump_file_map(
    results_dir: str | Path, extra_names: Iterable[str] | None = None
) -> dict[str, Any]:
    root = Path(results_dir)
    file_map = build_file_map(root, extra_names)
    view = materialize_logical_view(root, file_map)
    payload = {
        "results_dir": str(root.resolve()) if root.exists() else str(root),
        "file_map": file_map,
        "contract_view": view,
        "paper_strict": sorted(PAPER_STRICT_FILES),
    }
    out = root / FILE_MAP_NAME
    try:
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["map_path"] = str(out)
    except OSError:
        payload["map_path"] = None
    return payload


def parameters_from_recipe(recipe: dict[str, Any] | None) -> dict[str, Any]:
    """从 repro recipe 的 workflow_b.parameters 抽出进 B 的参数（多步时 LC-MS 步优先）。"""
    if not recipe:
        return {}
    from web_frontend.backend.agent_b.skill_param_inject import merge_param_dicts, parse_skill_parameters

    collected: dict[str, Any] = {"source": [recipe.get("recipe_id") or "recipe"]}
    lcms: dict[str, Any] = {}
    volatile: dict[str, Any] = {}
    for step in recipe.get("workflow_b") or []:
        if not isinstance(step, dict):
            continue
        params = dict(step.get("parameters") or {})
        blob = " ".join(
            [
                str(step.get("name") or ""),
                str(step.get("description") or ""),
                " ".join(str(x) for x in (step.get("software") or [])),
            ]
        )
        parsed = parse_skill_parameters(blob)
        merged = merge_param_dicts(parsed, params)
        name = str(step.get("name") or "").lower()
        soft = " ".join(str(x) for x in (step.get("software") or [])).lower()
        is_nonvolatile = (
            "lcms" in name
            or "mzmine" in soft
            or "nonvolatile" in name
            or "non-volatile" in name
        )
        is_volatile = (not is_nonvolatile) and (
            "gcms" in name
            or "gc-ms" in name
            or "gnps" in soft
            or "volatile" in name
        )
        if is_volatile:
            volatile = merge_param_dicts(volatile, merged)
        elif is_nonvolatile:
            lcms = merge_param_dicts(lcms, merged)
            if "mzmine" in soft:
                lcms["prefer_preprocess"] = "mzmine"
                lcms["rewrite_preprocess"] = True
        else:
            collected = merge_param_dicts(collected, merged)
    out = merge_param_dicts(collected, volatile, lcms)
    if volatile.get("vip_threshold") and lcms.get("vip_threshold"):
        out["vip_threshold"] = lcms["vip_threshold"]
        out["volatile_vip_threshold"] = volatile["vip_threshold"]
    scaling = str(out.get("pca_scaling") or "").lower()
    if scaling in {"uv", "unitvariance", "autoscale"}:
        out["scale_method"] = "autoscale"
    out.pop("pca_scaling", None)
    out.pop("hca_euclidean_cutoff", None)
    if out.get("plsda_permutation_n") and "n_permutations" not in out:
        out["n_permutations"] = int(out["plsda_permutation_n"])
    out.pop("plsda_permutation_n", None)
    return out


def collect_skill_parameters(
    *,
    goal_text: str = "",
    skill_text: str = "",
    recipe: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from web_frontend.backend.agent_b.skill_param_inject import merge_param_dicts, parse_skill_parameters

    parts = [parse_skill_parameters(skill_text), parse_skill_parameters(goal_text)]
    if plan:
        parts.append(parse_skill_parameters(str(plan.get("goal") or plan.get("objective") or "")))
        for step in plan.get("steps") or []:
            if isinstance(step, dict):
                parts.append(
                    parse_skill_parameters(
                        f"{step.get('description') or ''} {step.get('tools') or ''}"
                    )
                )
    recipe_params = parameters_from_recipe(recipe)
    merged = merge_param_dicts(*parts, recipe_params)
    sources: list[str] = []
    if recipe_params.get("source"):
        sources.extend(str(x) for x in recipe_params["source"])
    if skill_text.strip():
        sources.append("skill_text")
    merged["source"] = list(dict.fromkeys(sources))
    return merged


def bindings_document() -> list[dict[str, Any]]:
    rows = []
    for item in FILE_BINDINGS:
        row = asdict(item)
        row["paper_strict"] = item.logical_name in PAPER_STRICT_FILES
        rows.append(row)
    return rows
