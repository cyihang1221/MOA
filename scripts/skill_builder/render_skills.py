"""将 Recipe 渲染为 Agent 可注入的 Skill Markdown。"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Iterable

from parse_recipes import Recipe, WorkflowStep

# 论文专名触发词：仅靠领域词（PCA/GNPS）会命中共识 Skill，点名论文时必须能命中本篇。
PAPER_TRIGGER_ALIASES: dict[str, list[str]] = {
    "10.1016/j.fochx.2026.103843": [
        "都匀毛尖",
        "都匀毛尖茶",
        "Duyun Maojian",
        "Maojian",
        "五等级",
        "fochx",
        "103843",
    ],
}

# 文献软件名 → 当前 Agent B 可执行工具（写入 Skill，供 A 映射；禁止发明未注册工具）
LITERATURE_TOOL_MAP: list[tuple[str, str]] = [
    ("msconvert", "convert_raw_to_mzml_msconvert 或 convert_raw_to_mzml_ThermoRawFileParser"),
    ("mzmine", "data_preprocessing_mzmine（已注册且本机可运行时）；否则 data_preprocessing_xcms"),
    ("simca", "statistical_analysis_mixomics（LC-MS vip_threshold=1.2；GC-MS vip_threshold=1.5）"),
    ("metaboanalyst", "statistical_analysis_mixomics"),
    ("gnps", "molecular_networking_gnps / molecular_networking_fbmn"),
]


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", (text or "").strip())
    s = re.sub(r"_+", "_", s).strip("_").lower()
    return (s or "skill")[:max_len]


def infer_domain(recipe: Recipe) -> str:
    tools = " ".join(recipe.tools).lower()
    title = (recipe.paper_title or "").lower()
    blob = f"{tools} {title}"
    if any(k in tools for k in ("gnps", "fbmn", "ms2lda", "molnetenhancer")):
        return "molecular_networking"
    if any(k in blob for k in ("kegg", "enrichment", "pathway", "reactome", "ora")):
        return "pathway_enrichment"
    if any(k in tools for k in ("mixomics", "metaboanalyst", "simca", "metax", "ropls", "opls")):
        return "statistical_analysis"
    if "xcms" in tools or "mzmine" in tools or "openms" in tools:
        return "lcms_preprocessing"
    return "general_metabolomics"


def infer_triggers(recipe: Recipe) -> list[str]:
    keys: list[str] = []
    blob = f"{recipe.source_paper} {recipe.path} {recipe.paper_title}"
    for doi, aliases in PAPER_TRIGGER_ALIASES.items():
        if doi.lower() in blob.lower() or doi.replace("/", "_").lower() in blob.lower():
            keys.extend(aliases)
    for quoted in re.findall(r"[‘'\"«]([^'\"»]{3,40})[’'\"»]", recipe.paper_title or ""):
        q = quoted.strip()
        if q:
            keys.append(q)
    domain = infer_domain(recipe)
    domain_map = {
        "molecular_networking": ["分子网络", "GNPS", "FBMN", "molecular networking", "motif"],
        "statistical_analysis": ["统计分析", "PCA", "PLS-DA", "火山图", "VIP", "差异代谢物"],
        "pathway_enrichment": ["通路", "KEGG", "富集", "pathway", "enrichment"],
        "lcms_preprocessing": ["峰检测", "XCMS", "预处理", "peak picking", "alignment"],
        "general_metabolomics": ["代谢组", "metabolomics", "LC-MS"],
    }
    keys.extend(domain_map.get(domain, []))
    for tool in recipe.tools[:8]:
        t = tool.strip()
        # 只保留短主工具名，避免把整句参数/仪器型号塞进触发器
        main = re.split(r"[\(/,;]", t)[0].strip()
        token = main.split()[0] if main else ""
        if 3 <= len(token) <= 24 and token.lower() not in {
            "custom",
            "python",
            "r",
            "script",
            "metadata.csv",
        }:
            if "." in token and not token.lower().startswith("ms"):
                continue
            keys.append(token)
    # 去重保序（不做整句标题分词，避免误触发）
    seen = set()
    out = []
    for k in keys:
        kl = k.lower()
        if kl in seen:
            continue
        seen.add(kl)
        out.append(k)
    return out[:20]


def _analysis_goal(recipe: Recipe) -> str:
    title = recipe.paper_title or "Untargeted metabolomics analysis"
    return (
        f"复现/对齐文献研究目标：{title}。"
        "按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。"
    )


def render_paper_skill(recipe: Recipe) -> str:
    domain = infer_domain(recipe)
    lines = [
        f"# Skill: {recipe.paper_title or 'Untitled paper skill'}",
        "",
        f"- **skill_type**: paper_recipe",
        f"- **functional_domain**: `{domain}`",
        f"- **reproducibility_score**: {recipe.reproducibility_score}/100",
        f"- **source**: {recipe.source_paper or recipe.path}",
        "",
        "## Analysis Goal",
        _analysis_goal(recipe),
        "",
        "## Pipeline Coverage（含软件参数）",
        "",
        "| Step | Task | Tool | Algorithm | Parameters |",
        "|------|------|------|-----------|------------|",
    ]
    for s in recipe.steps:
        params = (s.parameters or "—").replace("|", "\\|")
        tool = (s.tool or "—").replace("|", "\\|")
        algo = (s.algorithm or "—").replace("|", "\\|")
        title = (s.title or "—").replace("|", "\\|")
        lines.append(f"| {s.index} | {title} | {tool} | {algo} | `{params}` |")

    lines += ["", "## Expected Figures（目的→图→解读）", ""]
    if recipe.figures:
        lines += [
            "| Figure | Type | Why / Caption | How to read / stats | Produced by |",
            "|---------|------|---------------|---------------------|-------------|",
        ]
        for fig in recipe.figures:
            cap = (fig.caption or "—").replace("|", "\\|")
            how = (fig.statistical_test or fig.visualization_tool or "—").replace("|", "\\|")
            lines.append(
                f"| {fig.name} | {fig.fig_type or '—'} | {cap} | {how} | {fig.produced_by_step or '—'} |"
            )
    else:
        lines.append(
            "文献配方未结构化出图字段；请根据 Pipeline 输出推断："
            "预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。"
        )

    lines += ["", "## Parameter Highlights", ""]
    param_steps = recipe.param_steps
    if param_steps:
        for s in param_steps:
            lines.append(f"- **Step {s.index} ({s.tool or s.title})**: `{s.parameters}`")
    else:
        lines.append("- （本条配方未解析到显式 parameters 字段）")

    if recipe.strengths:
        lines += ["", "## Reproducibility Notes", ""]
        for item in recipe.strengths[:8]:
            lines.append(f"- {item}")

    mapped = []
    tools_l = " ".join(recipe.tools).lower()
    for needle, dest in LITERATURE_TOOL_MAP:
        if needle in tools_l:
            mapped.append(f"- `{needle}` → {dest}")

    lines += [
        "",
        "## Agent Usage Notes",
        "- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。",
        "- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。",
        "- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。",
        "- 湿法/细胞/斑马鱼/国标感官不得写成 Agent B 可执行步，除非用户已上传对应结果表。",
        "- 以实际 metadata 分组为准；论文五等级设计与 BK/DY/QC 会话不是同一实验。",
        "",
    ]
    if mapped:
        lines += ["## Available-tool mapping", *mapped, ""]
    return "\n".join(lines)


def _norm_param_key(tool: str, parameters: str) -> str:
    return f"{(tool or '').strip().lower()}||{(parameters or '').strip()}"


def build_consensus_skill(
    *,
    name: str,
    domain: str,
    recipes: list[Recipe],
    trigger_keywords: list[str],
) -> str:
    """多篇配方共识：按工具聚合高频参数。"""
    tool_counter: Counter[str] = Counter()
    param_counter: Counter[str] = Counter()
    param_examples: dict[str, list[str]] = defaultdict(list)
    figure_types: Counter[str] = Counter()
    sources: list[str] = []

    for r in recipes:
        sources.append(r.source_paper or r.paper_title or r.path)
        for t in r.tools:
            tool_counter[t] += 1
        for s in r.param_steps:
            key = _norm_param_key(s.tool, s.parameters)
            param_counter[key] += 1
            if len(param_examples[key]) < 3:
                param_examples[key].append(r.source_paper or r.paper_title)
        for f in r.figures:
            if f.fig_type:
                figure_types[f.fig_type.lower()] += 1
            elif f.name:
                figure_types[f.name.split(":")[0].strip().lower()] += 1

    lines = [
        f"# Skill: {name}",
        "",
        f"- **skill_type**: multi_paper_consensus",
        f"- **functional_domain**: `{domain}`",
        f"- **n_papers**: {len(recipes)}",
        f"- **trigger_keywords**: {', '.join(trigger_keywords)}",
        "",
        "## Analysis Goal",
        f"当用户目标匹配「{name}」场景时，采用多篇高水平文献的工具偏好与参数共识，"
        "规划分析流程并产出对应科研图与解释。",
        "",
        "## Tool Preference Order",
        "",
    ]
    for tool, cnt in tool_counter.most_common(12):
        lines.append(f"- `{tool}` （出现于 {cnt}/{len(recipes)} 篇）")

    lines += ["", "## Parameter Consensus（按出现频次）", ""]
    for key, cnt in param_counter.most_common(20):
        tool, params = key.split("||", 1)
        if not params:
            continue
        lines.append(f"- **{tool or 'unknown'}** `{params}` — {cnt} 篇共识")
        for src in param_examples.get(key, [])[:2]:
            lines.append(f"  - source: {src}")

    lines += ["", "## Expected Figures Consensus", ""]
    if figure_types:
        for ft, cnt in figure_types.most_common(10):
            lines.append(f"- `{ft}` （{cnt} 次）")
    else:
        lines.append("- PCA / PLS-DA scores、volcano、heatmap、pathway bubble、network topology（按场景裁剪）")

    lines += ["", "## Representative Sources", ""]
    for src in sources[:12]:
        lines.append(f"- {src}")

    lines += [
        "",
        "## Agent Usage Notes",
        "- 参数冲突时：多篇共识 > 单篇报告 > 工具默认值。",
        "- 必须映射到系统可用工具名；不可发明未注册工具。",
        "- 出图与解释服务于用户分析目的，不只做样式改图。",
        "",
    ]
    return "\n".join(lines)


def pick_scenario_groups(recipes: Iterable[Recipe]) -> dict[str, list[Recipe]]:
    groups: dict[str, list[Recipe]] = defaultdict(list)
    for r in recipes:
        groups[infer_domain(r)].append(r)
    return dict(groups)
