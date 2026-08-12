"""解析 softwares_database/repro_recipes 中的可复现配方文本。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class WorkflowStep:
    index: int
    title: str
    tool: str = ""
    algorithm: str = ""
    parameters: str = ""
    input_desc: str = ""
    output_desc: str = ""
    confidence: str = ""


@dataclass
class FigureSpec:
    name: str
    fig_type: str = ""
    caption: str = ""
    produced_by_step: str = ""
    visualization_tool: str = ""
    statistical_test: str = ""


@dataclass
class Recipe:
    path: str
    paper_title: str = ""
    source_paper: str = ""
    reproducibility_score: int = 0
    steps: list[WorkflowStep] = field(default_factory=list)
    figures: list[FigureSpec] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    raw_text: str = ""

    @property
    def tools(self) -> list[str]:
        seen: list[str] = []
        for step in self.steps:
            tool = (step.tool or "").strip()
            if not tool:
                continue
            # 取主工具名（去掉括号版本）
            main = re.split(r"[\(/,]", tool)[0].strip()
            if main and main not in seen:
                seen.append(main)
        return seen

    @property
    def param_steps(self) -> list[WorkflowStep]:
        return [s for s in self.steps if (s.parameters or "").strip()]


_ENTRY_SPLIT = re.compile(r"={5,}\s*reproducibility_recipe entry\s*={5,}", re.I)
_SCORE_RE = re.compile(r"overall_reproducibility_score:\s*(\d+)\s*/\s*100", re.I)
_STEP_RE = re.compile(r"^\s*Step\s+(\d+):\s*(.+)$", re.I | re.M)
_FIG_RE = re.compile(
    r"^\s*(Figure[^:\n]+|Extended Data Fig\.[^:\n]+|Fig\.[^:\n]+):\s*\[([^\]]*)\]\s*$",
    re.I | re.M,
)


def _field(block: str, key: str) -> str:
    # 配方字段常有缩进（如 "    parameters: ..."）
    m = re.search(rf"^[ \t]*{re.escape(key)}:\s*(.*)$", block, re.I | re.M)
    return (m.group(1).strip() if m else "")


def _parse_steps(block: str) -> list[WorkflowStep]:
    steps: list[WorkflowStep] = []
    matches = list(_STEP_RE.finditer(block))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
        # 截断到 figures / reproducibility_strengths
        chunk = block[start:end]
        for pat in (r"\nfigures:", r"\nreproducibility_strengths:", r"\n\[figures\]"):
            sm = re.search(pat, chunk, re.I)
            if sm:
                chunk = chunk[: sm.start()]
                break
        body = chunk
        steps.append(
            WorkflowStep(
                index=int(m.group(1)),
                title=m.group(2).strip(),
                tool=_field(body, "tool"),
                algorithm=_field(body, "algorithm"),
                parameters=_field(body, "parameters"),
                input_desc=_field(body, "input"),
                output_desc=_field(body, "output"),
                confidence=_field(body, "confidence"),
            )
        )
    return steps


def _parse_figures(block: str) -> list[FigureSpec]:
    figs: list[FigureSpec] = []
    # 优先 figures: 段
    fig_sec = block
    msec = re.search(r"(?:^figures:|^\s*\[figures\])\s*", block, re.I | re.M)
    if msec:
        fig_sec = block[msec.end() :]
        cut = re.search(r"^reproducibility_strengths:", fig_sec, re.I | re.M)
        if cut:
            fig_sec = fig_sec[: cut.start()]

    matches = list(_FIG_RE.finditer(fig_sec))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(fig_sec)
        body = fig_sec[start:end]
        figs.append(
            FigureSpec(
                name=m.group(1).strip(),
                fig_type=(m.group(2) or "").strip(),
                caption=_field(body, "caption"),
                produced_by_step=_field(body, "produced_by_step"),
                visualization_tool=_field(body, "visualization_tool"),
                statistical_test=_field(body, "statistical_test"),
            )
        )
    return figs


def _parse_strengths(block: str) -> list[str]:
    m = re.search(r"reproducibility_strengths:\s*(.*)$", block, re.I | re.S)
    if not m:
        return []
    out = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("-"):
            out.append(line.lstrip("- ").strip())
    return out


def parse_recipe_file(path: Path) -> list[Recipe]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    parts = _ENTRY_SPLIT.split(text)
    recipes: list[Recipe] = []
    # 第一部分可能是文件头
    blocks = parts[1:] if len(parts) > 1 else ([text] if "workflow_steps" in text else [])
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        score_m = _SCORE_RE.search(block)
        score = int(score_m.group(1)) if score_m else 0
        recipes.append(
            Recipe(
                path=str(path),
                paper_title=_field(block, "paper_title"),
                source_paper=_field(block, "source_paper"),
                reproducibility_score=score,
                steps=_parse_steps(block),
                figures=_parse_figures(block),
                strengths=_parse_strengths(block),
                raw_text=block,
            )
        )
    return recipes


def load_recipes(recipes_dir: Path) -> list[Recipe]:
    out: list[Recipe] = []
    for path in sorted(recipes_dir.glob("recipe_*.txt")):
        try:
            out.extend(parse_recipe_file(path))
        except Exception as exc:
            print(f"[skill_builder] skip {path.name}: {exc}")
    return out


def recipe_to_dict(recipe: Recipe) -> dict[str, Any]:
    return {
        "path": recipe.path,
        "paper_title": recipe.paper_title,
        "source_paper": recipe.source_paper,
        "reproducibility_score": recipe.reproducibility_score,
        "tools": recipe.tools,
        "steps": [
            {
                "index": s.index,
                "title": s.title,
                "tool": s.tool,
                "algorithm": s.algorithm,
                "parameters": s.parameters,
                "input": s.input_desc,
                "output": s.output_desc,
                "confidence": s.confidence,
            }
            for s in recipe.steps
        ],
        "figures": [
            {
                "name": f.name,
                "type": f.fig_type,
                "caption": f.caption,
                "produced_by_step": f.produced_by_step,
                "visualization_tool": f.visualization_tool,
                "statistical_test": f.statistical_test,
            }
            for f in recipe.figures
        ],
        "strengths": recipe.strengths,
    }
