"""把 Agent A 的方案解析成 C 可消费的规范化 JSON。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from web_frontend.backend.agent_c.plan_adapter import (
    attach_source_files,
    is_massomics_plan_document,
    normalize_massomics_plan,
    parse_massomics_markdown,
)
from web_frontend.backend.agent_c.contract import (
    CONTRACT_VERSION,
    PLAN_SECTION_ALIASES,
    empty_figure_spec,
    empty_plan,
)
from web_frontend.backend.plot_edit_registry import (
    PLOT_ALIASES,
    PLOT_SPECS,
    get_plot_spec,
    plot_type_from_stem,
    stem_prefix_for_plot_type,
)

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.M)
_FIGURE_LINE_RE = re.compile(
    r"^(?:#{0,4}\s*)?(?:figure|fig\.?|图)\s*([A-Za-z]?\d+)\s*[:：.\-]?\s*(.*)$",
    re.I,
)
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}")


def resolve_plot_type(text: str | None) -> str | None:
    """把方案里的图型描述映射到 PlotSpec.plot_type。"""
    raw = (text or "").strip()
    if not raw:
        return None
    key = raw.lower().replace(" ", "_").replace("-", "_")
    spec = get_plot_spec(raw) or get_plot_spec(key)
    if spec:
        return spec.plot_type
    from_stem = plot_type_from_stem(key)
    if from_stem:
        return from_stem
    lower = raw.lower()
    for alias, stem in sorted(PLOT_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if alias.lower() == lower or alias.lower() in lower:
            from_alias = plot_type_from_stem(stem)
            if from_alias:
                return from_alias
            alias_spec = get_plot_spec(stem) or get_plot_spec(stem.replace("_plot", ""))
            if alias_spec:
                return alias_spec.plot_type
    # stem 直接命中
    for spec in PLOT_SPECS:
        if spec.stem_prefix in key or spec.plot_type == key:
            return spec.plot_type
        if spec.default_title.lower() in lower:
            return spec.plot_type
    return None


def resolve_all_plot_types(text: str | None) -> list[str]:
    """从一段步骤/预期输出描述中抽出全部可识别图类型。"""
    raw = (text or "").strip()
    if not raw:
        return []
    found: list[str] = []
    lower = raw.lower()
    for alias, stem in sorted(PLOT_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if alias.lower() not in lower:
            continue
        pt = plot_type_from_stem(stem)
        if not pt:
            spec = get_plot_spec(stem) or get_plot_spec(stem.replace("_plot", ""))
            pt = spec.plot_type if spec else None
        if pt and pt not in found:
            found.append(pt)
    return found


def _normalize_heading(title: str) -> str | None:
    t = re.sub(r"^[\d.、\s]+", "", (title or "").strip()).lower()
    t = t.replace("_", " ")
    for field, aliases in PLAN_SECTION_ALIASES.items():
        for alias in aliases:
            if t == alias or t.startswith(alias) or alias in t:
                return field
    return None


def _split_markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = "_preamble"
    sections[current] = []
    for line in (text or "").splitlines():
        m = _HEADING_RE.match(line)
        if m:
            field = _normalize_heading(m.group(2))
            if field:
                current = field
                sections.setdefault(current, [])
                continue
        sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}


def _parse_json_block(text: str) -> Any | None:
    blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text or "", re.I)
    for block in blocks:
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue
    stripped = (text or "").strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return None
    return None


def _figure_from_mapping(item: dict[str, Any], index: int) -> dict:
    fig = empty_figure_spec()
    fig["figure_id"] = str(
        item.get("figure_id") or item.get("id") or item.get("图号") or f"Figure {index}"
    )
    fig["title"] = str(item.get("title") or item.get("标题") or item.get("theme") or "").strip()
    plot_raw = str(
        item.get("plot_type")
        or item.get("type")
        or item.get("图型")
        or item.get("chart")
        or ""
    ).strip()
    fig["plot_type"] = resolve_plot_type(plot_raw) or ""
    fig["stem"] = stem_prefix_for_plot_type(fig["plot_type"]) or ""
    fig["theme"] = str(item.get("theme") or item.get("总体主题") or fig["title"]).strip()
    fig["logic"] = str(item.get("logic") or item.get("核心逻辑链") or "").strip()
    fig["purpose"] = str(item.get("purpose") or item.get("存在理由") or "").strip()
    fig["expected_observation"] = str(
        item.get("expected_observation") or item.get("预期观察") or item.get("expected") or ""
    ).strip()
    try:
        fig["source_step"] = int(item.get("source_step") or 0)
    except (TypeError, ValueError):
        fig["source_step"] = 0
    sf = item.get("source_files") or []
    fig["source_files"] = [str(f) for f in sf] if isinstance(sf, list) else []
    fig["description"] = str(item.get("description") or "").strip()
    panels = item.get("panels") or item.get("panel") or []
    if isinstance(panels, list):
        fig["panels"] = [p for p in panels if isinstance(p, dict)]
    hint = item.get("plot_config_hint") or item.get("plot_config") or {}
    fig["plot_config_hint"] = hint if isinstance(hint, dict) else {}
    if not fig["title"]:
        fig["title"] = fig["theme"] or fig["figure_id"]
    return fig


def _parse_markdown_table(section: str) -> list[dict]:
    rows: list[dict] = []
    lines = [ln.strip() for ln in section.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 2:
        return rows
    headers = [c.strip() for c in lines[0].strip("|").split("|")]
    body = lines[1:]
    if body and _TABLE_SEP_RE.match(body[0].replace("|", " ").strip() or "---"):
        body = body[1:]
    for i, line in enumerate(body, start=1):
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 2:
            continue
        mapping = {headers[j]: cols[j] if j < len(cols) else "" for j in range(len(headers))}
        # 常见列表头
        item = {
            "figure_id": mapping.get("图号") or mapping.get("figure") or mapping.get("id") or f"Figure {i}",
            "plot_type": mapping.get("图型") or mapping.get("type") or mapping.get("chart") or "",
            "theme": mapping.get("用途") or mapping.get("总体主题") or mapping.get("theme") or "",
            "expected_observation": mapping.get("预期观察") or mapping.get("expected") or "",
            "title": mapping.get("标题") or mapping.get("title") or "",
            "purpose": mapping.get("存在理由") or mapping.get("purpose") or "",
            "logic": mapping.get("核心逻辑链") or mapping.get("logic") or "",
        }
        rows.append(_figure_from_mapping(item, i))
    return rows


def _parse_figure_lines(section: str) -> list[dict]:
    figures: list[dict] = []
    current: dict | None = None
    for line in section.splitlines():
        m = _FIGURE_LINE_RE.match(line.strip())
        if m:
            if current:
                if current.get("purpose") or current.get("expected_observation"):
                    panels = current.setdefault("panels", [])
                    if not panels:
                        panels.append({})
                    panel = panels[0]
                    panel.setdefault("panel_id", "A")
                    if current.get("purpose"):
                        panel.setdefault("purpose", current["purpose"])
                    if current.get("expected_observation"):
                        panel.setdefault("expected_observation", current["expected_observation"])
                figures.append(current)
            rest = m.group(2).strip()
            current = _figure_from_mapping(
                {
                    "figure_id": f"Figure {m.group(1)}",
                    "title": rest,
                    "plot_type": rest,
                    "theme": rest,
                },
                len(figures) + 1,
            )
            current["raw"] = line
            continue
        if current is None:
            continue
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            body = stripped[2:]
            value = re.sub(r"^[^:：]*[:：]", "", body).strip() or body
            low = body.lower()
            if "图型" in body or (low.startswith("type") and "purpose" not in low):
                pt = resolve_plot_type(value)
                if pt:
                    current["plot_type"] = pt
                    current["stem"] = stem_prefix_for_plot_type(pt) or ""
            elif "主题" in body or "theme" in low:
                current["theme"] = value
            elif "逻辑" in body or "logic" in low:
                current["logic"] = value
            elif "purpose" in low or ("目的" in body and "预期" not in body):
                current["purpose"] = value
            elif "建议设计" in body or "design" in low:
                current.setdefault("panels", [])
                if not current["panels"]:
                    current["panels"] = [{}]
                current["panels"][0]["design"] = value
            elif "存在理由" in body or "rationale" in low:
                current.setdefault("panels", [])
                if not current["panels"]:
                    current["panels"] = [{}]
                current["panels"][0]["rationale"] = value
            elif "预期" in body or "observe" in low:
                current["expected_observation"] = value
    if current:
        if current.get("purpose") or current.get("expected_observation"):
            panels = current.setdefault("panels", [])
            if not panels:
                panels.append({})
            panel = panels[0]
            panel.setdefault("panel_id", "A")
            if current.get("purpose"):
                panel.setdefault("purpose", current["purpose"])
            if current.get("expected_observation"):
                panel.setdefault("expected_observation", current["expected_observation"])
        figures.append(current)
    return figures


def _figures_from_visualization_section(section: str) -> list[dict]:
    blob = _parse_json_block(section)
    if isinstance(blob, list):
        return [_figure_from_mapping(x, i + 1) for i, x in enumerate(blob) if isinstance(x, dict)]
    if isinstance(blob, dict) and isinstance(blob.get("figures") or blob.get("required_visualization"), list):
        items = blob.get("figures") or blob.get("required_visualization")
        return [_figure_from_mapping(x, i + 1) for i, x in enumerate(items) if isinstance(x, dict)]
    table_figs = _parse_markdown_table(section)
    if table_figs:
        return table_figs
    return _parse_figure_lines(section)


def _workflow_from_legacy_stages(stages: list) -> list[dict]:
    steps = []
    for i, item in enumerate(stages, start=1):
        if not isinstance(item, dict):
            steps.append({"step_id": i, "task": str(item), "expected_output": ""})
            continue
        steps.append(
            {
                "step_id": i,
                "stage": item.get("stage") or f"Stage {i}",
                "objective": item.get("objective") or "",
                "task": item.get("task") or item.get("operations") or "",
                "input": item.get("input") or item.get("Input") or "",
                "operations": item.get("operations") or item.get("task") or "",
                "output": item.get("output") or item.get("expected_output") or "",
                "tools": item.get("tools") or item.get("tool") or "",
                "expected_output": item.get("expected_output") or "",
                "quality_check": item.get("quality_check") or "",
            }
        )
    return steps


def _figures_from_legacy_stages(stages: list) -> list[dict]:
    """旧版 analysis_plan.json 没有独立出图清单时，从 expected_output/task 推断。"""
    figures: list[dict] = []
    seen: set[str] = set()
    for item in stages:
        text = ""
        if isinstance(item, dict):
            text = " ".join(
                str(item.get(k) or "")
                for k in ("task", "expected_output", "quality_check", "stage")
            )
        else:
            text = str(item)
        plot_types = resolve_all_plot_types(text)
        for plot_type in plot_types:
            if plot_type in seen:
                continue
            seen.add(plot_type)
            stem = stem_prefix_for_plot_type(plot_type) or plot_type
            figures.append(
                _figure_from_mapping(
                    {
                        "figure_id": f"Figure {len(figures) + 1}",
                        "plot_type": plot_type,
                        "title": stem,
                        "theme": f"由执行步骤推断：需要 {plot_type} 图",
                    },
                    len(figures) + 1,
                )
            )
    return figures


def _looks_like_path(value: str) -> bool:
    if not value or "\n" in value or len(value) > 512:
        return False
    path = Path(value)
    if path.suffix.lower() in {".md", ".json", ".txt", ".markdown"}:
        return True
    return path.exists()


def _apply_canonical_dict(plan: dict[str, Any], data: dict[str, Any], warnings: list[str]) -> None:
    """把 canonical / 已规范化的 dict 写入 plan。"""
    plan["plan_format"] = str(data.get("plan_format") or "fr2")
    plan["objective"] = str(data.get("objective") or "")
    plan["data_understanding"] = str(data.get("data_understanding") or "")
    plan["workflow"] = data.get("workflow") if isinstance(data.get("workflow"), list) else []
    plan["tools_required"] = data.get("tools_required") or ""
    plan["expected_results"] = data.get("expected_results") or ""
    viz = data.get("required_visualization") or data.get("figures") or data.get("visualizations") or []
    if isinstance(viz, list):
        plan["required_visualization"] = [
            _figure_from_mapping(x, i + 1) for i, x in enumerate(viz) if isinstance(x, dict)
        ]
    elif isinstance(viz, str):
        plan["required_visualization"] = _figures_from_visualization_section(viz)
    interps = data.get("interpretations") or []
    plan["interpretations"] = interps if isinstance(interps, list) else []
    plan["interpretation_guideline"] = str(data.get("interpretation_guideline") or "")
    if not plan["interpretation_guideline"] and plan["interpretations"]:
        from web_frontend.backend.agent_c.plan_adapter import _interpretations_to_guideline

        plan["interpretation_guideline"] = _interpretations_to_guideline(plan["interpretations"])
    rp = data.get("reporting_plan") or data.get("report")
    if isinstance(rp, dict):
        plan["reporting_plan"].update({k: rp[k] for k in rp if k in plan["reporting_plan"] or True})
        plan["reporting_plan"]["language"] = str(rp.get("language") or "zh")
        if isinstance(rp.get("sections"), list):
            plan["reporting_plan"]["sections"] = [str(s) for s in rp["sections"]]
        plan["reporting_plan"]["notes"] = str(rp.get("notes") or plan["reporting_plan"].get("notes") or "")
        plan["reporting_plan"]["audience"] = str(rp.get("audience") or "")
        plan["reporting_plan"]["decision_to_report"] = str(rp.get("decision_to_report") or "")
        if isinstance(rp.get("references"), list):
            plan["reporting_plan"]["references"] = [str(r) for r in rp["references"]]
    elif isinstance(rp, str):
        plan["reporting_plan"]["notes"] = rp
    for key in ("risks", "assumptions", "references"):
        val = data.get(key)
        if isinstance(val, list):
            plan[key] = [str(v) for v in val]
    if data.get("reproduction_target"):
        plan["reproduction_target"] = dict(data["reproduction_target"])
    if data.get("figure_blueprint"):
        plan["figure_blueprint"] = dict(data["figure_blueprint"])


def parse_plan(source: str | Path | dict[str, Any] | list) -> dict[str, Any]:
    """解析 A 的方案为规范化 plan 对象。"""
    plan = empty_plan()
    warnings: list[str] = []
    data: Any = None
    md_sections: dict[str, str] = {}
    text = ""

    if isinstance(source, dict):
        data = source
        plan["source"] = {"format": "dict", "path": ""}
    elif isinstance(source, list):
        data = source
        plan["source"] = {"format": "list", "path": ""}
    else:
        path: Path | None = None
        if isinstance(source, Path) or (isinstance(source, str) and _looks_like_path(source)):
            path = Path(source)
        if path is not None and path.is_file():
            text = path.read_text(encoding="utf-8")
            plan["source"] = {
                "format": path.suffix.lower().lstrip("."),
                "path": str(path),
            }
        else:
            text = str(source)
            plan["source"] = {"format": "text", "path": ""}
        stripped = text.strip()
        if (path is not None and path.suffix.lower() == ".json") or stripped.startswith("{") or stripped.startswith("["):
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                warnings.append(f"JSON 解析失败，按 Markdown 处理: {exc}")
                data = None
                md_sections = _split_markdown_sections(text)
        else:
            md_sections = _split_markdown_sections(text)

    if isinstance(data, dict) and is_massomics_plan_document(data):
        data = normalize_massomics_plan(data)
        warnings.append("已识别 MassOmics PlanDocument，已映射为 C canonical 字段")

    # canonical object
    if isinstance(data, dict) and (
        "required_visualization" in data or "objective" in data or "reporting_plan" in data
    ):
        _apply_canonical_dict(plan, data, warnings)
    elif isinstance(data, dict) and isinstance(data.get("plan"), list):
        plan["workflow"] = _workflow_from_legacy_stages(data["plan"])
        plan["objective"] = str(data.get("goal") or data.get("objective") or "")
        plan["required_visualization"] = _figures_from_legacy_stages(data["plan"])
        warnings.append("识别为旧版 {plan: [...]} ，出图清单由步骤文本推断")
    elif isinstance(data, list):
        plan["workflow"] = _workflow_from_legacy_stages(data)
        plan["required_visualization"] = _figures_from_legacy_stages(data)
        warnings.append("识别为旧版阶段列表 analysis_plan.json，出图清单由步骤文本推断")
    else:
        # markdown / 纯文本
        fallback = text or (str(source) if not isinstance(source, (dict, list)) else "")
        massomics = None
        if any(k in fallback for k in ("分析目标", "分析工作流", "可视化方案", "代谢组学分析计划")):
            massomics = parse_massomics_markdown(fallback)
        if massomics:
            _apply_canonical_dict(plan, massomics, warnings)
            warnings.append("已识别 MassOmics Markdown 计划，已映射为 C canonical 字段")
        else:
            sections = md_sections or _split_markdown_sections(fallback)
            if sections and not plan.get("objective") and not plan.get("required_visualization"):
                plan["objective"] = sections.get("objective") or ""
                plan["data_understanding"] = sections.get("data_understanding") or ""
                plan["tools_required"] = sections.get("tools_required") or ""
                plan["expected_results"] = sections.get("expected_results") or ""
                plan["interpretation_guideline"] = sections.get("interpretation_guideline") or ""
                plan["reporting_plan"]["notes"] = sections.get("reporting_plan") or ""
                wf = sections.get("workflow") or ""
                plan["workflow"] = [{"step_id": 1, "task": wf}] if wf else []
                viz = sections.get("required_visualization") or ""
                plan["required_visualization"] = _figures_from_visualization_section(viz) if viz else []
                if not plan["required_visualization"] and not plan["objective"]:
                    warnings.append(
                        "未能识别标准方案章节，请改用 canonical JSON、MassOmics plan JSON 或带标准标题的 Markdown"
                    )

    # 补 stem
    for fig in plan["required_visualization"]:
        if fig.get("plot_type") and not fig.get("stem"):
            fig["stem"] = stem_prefix_for_plot_type(str(fig["plot_type"])) or ""

    if not plan["required_visualization"]:
        warnings.append("方案中没有可解析的出图清单；run 时需 figure_mode=available 才会按 B 的结果出图")

    attach_source_files(plan)

    plan["contract_version"] = CONTRACT_VERSION
    plan["warnings"] = warnings
    return plan


def load_plan(path: str | Path) -> dict[str, Any]:
    return parse_plan(Path(path))
