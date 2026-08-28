"""论文复现配方：加载 repro recipe → 生成 Agent C 可消费方案 + 清点 checklist。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from web_frontend.backend.agent_c.contract import CONTRACT_VERSION, empty_figure_spec, empty_plan
from web_frontend.backend.plot_edit_registry import stem_prefix_for_plot_type

_RECIPES_DIR = Path(__file__).resolve().parent / "repro_recipes"


def list_repro_recipes() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not _RECIPES_DIR.is_dir():
        return out
    for path in sorted(_RECIPES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        paper = data.get("paper") or {}
        out.append(
            {
                "recipe_id": data.get("recipe_id") or path.stem,
                "title": paper.get("short_title") or paper.get("title") or path.stem,
                "doi": paper.get("doi") or "",
                "n_figures": len(data.get("figures") or []),
                "path": str(path),
            }
        )
    return out


def load_repro_recipe(recipe_id: str) -> dict[str, Any]:
    rid = (recipe_id or "").strip()
    if not rid:
        raise ValueError("recipe_id 不能为空")
    direct = _RECIPES_DIR / f"{rid}.json"
    if direct.is_file():
        return json.loads(direct.read_text(encoding="utf-8"))
    for path in _RECIPES_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(data.get("recipe_id") or path.stem) == rid:
            return data
    raise FileNotFoundError(f"未找到复现配方: {rid}")


def recipe_to_canonical_plan(recipe: dict[str, Any]) -> dict[str, Any]:
    """把 repro recipe 转为 Agent C parse_plan 可消费的 canonical plan。"""
    paper = recipe.get("paper") or {}
    plan = empty_plan()
    plan["plan_format"] = "paper_reproduction"
    plan["objective"] = (
        f"复现论文：{paper.get('short_title') or paper.get('title') or ''} "
        f"(DOI {paper.get('doi') or '—'})"
    ).strip()
    plan["data_understanding"] = str(recipe.get("study_design") or "")
    plan["workflow"] = list(recipe.get("workflow_b") or [])
    plan["tools_required"] = "见 workflow_b（Agent B 执行）"
    plan["expected_results"] = ", ".join(
        sorted(
            {
                f
                for fig in (recipe.get("figures") or [])
                for f in (fig.get("source_files") or [])
            }
        )
    )
    plan["reproduction_target"] = {
        "recipe_id": recipe.get("recipe_id") or "",
        "doi": paper.get("doi") or "",
        "pii": paper.get("pii") or "",
        "journal": paper.get("journal") or "",
        "local_pdf": paper.get("local_pdf") or "",
    }
    plan["agent_boundaries"] = recipe.get("agent_boundaries") or {}

    figures: list[dict[str, Any]] = []
    for fig in recipe.get("figures") or []:
        if not isinstance(fig, dict):
            continue
        plot_type = str(fig.get("plot_type") or "")
        spec = empty_figure_spec(
            figure_id=str(fig.get("figure_id") or ""),
            title=str(fig.get("title") or ""),
            plot_type=plot_type,
        )
        spec["stem"] = fig.get("stem") or stem_prefix_for_plot_type(plot_type) or plot_type
        spec["source_files"] = list(fig.get("source_files") or [])
        spec["panels"] = list(fig.get("panels") or [])
        spec["plot_config_hint"] = dict(fig.get("plot_config_hint") or {})
        spec["purpose"] = f"论文 {fig.get('figure_id') or ''} 复现"
        spec["paper_ref"] = paper.get("doi") or ""
        figures.append(spec)
    plan["required_visualization"] = figures

    reporting = plan.get("reporting_plan") or {}
    reporting["sections"] = list(recipe.get("report_sections") or reporting.get("sections") or [])
    reporting["references"] = [paper.get("doi") or ""]
    reporting["decision_to_report"] = (
        "按论文 Fig 1–8 顺序组织结果；图注引用方案与 B 产出文件计数，不臆造显著性。"
    )
    plan["reporting_plan"] = reporting
    plan["references"] = [paper.get("doi") or ""]
    plan["source"] = {"format": "paper_reproduction", "recipe_id": recipe.get("recipe_id") or ""}
    plan["contract_version"] = CONTRACT_VERSION
    plan["data_contract"] = recipe.get("data_contract") or {}
    return plan


def checklist_inventory(recipe: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    """对照 recipe 检查 B 侧必需文件是否齐全。"""
    root = Path(str(inventory.get("results_dir") or ""))
    names = {str(f.get("name") or "") for f in (inventory.get("files") or [])}
    required: set[str] = set()
    for fig in recipe.get("figures") or []:
        for sf in fig.get("source_files") or []:
            required.add(str(sf))
    optional_b = {
        str(step.get("outputs")[0])
        for step in (recipe.get("workflow_b") or [])
        if isinstance(step, dict) and step.get("outputs")
    }
    required |= optional_b

    present = sorted(f for f in required if f in names)
    missing = sorted(f for f in required if f not in names)
    figure_status: list[dict[str, Any]] = []
    for fig in recipe.get("figures") or []:
        sfs = [str(x) for x in (fig.get("source_files") or [])]
        fig_missing = [f for f in sfs if f not in names]
        figure_status.append(
            {
                "figure_id": fig.get("figure_id"),
                "plot_type": fig.get("plot_type"),
                "ready": not fig_missing,
                "missing_files": fig_missing,
            }
        )
    return {
        "recipe_id": recipe.get("recipe_id") or "",
        "doi": (recipe.get("paper") or {}).get("doi") or "",
        "required_files": sorted(required),
        "present": present,
        "missing": missing,
        "completion_rate": round(len(present) / len(required), 3) if required else 0.0,
        "figures": figure_status,
        "n_ready_figures": sum(1 for f in figure_status if f.get("ready")),
        "n_total_figures": len(figure_status),
    }


__all__ = [
    "list_repro_recipes",
    "load_repro_recipe",
    "recipe_to_canonical_plan",
    "checklist_inventory",
]
