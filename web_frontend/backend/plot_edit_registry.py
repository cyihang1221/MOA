"""可 Agent 改图的类型注册与目标解析。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from web_frontend.backend.session_storage import EDITED_PLOTS_SUBDIR

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True)
class PlotSpec:
    plot_type: str
    stem_prefix: str
    default_title: str
    data_files: tuple[str, ...]
    color_keys_hint: str


PLOT_SPECS: tuple[PlotSpec, ...] = (
    PlotSpec("pca", "pca_plot", "PCA", ("pca_scores.csv",), "分组名（metadata Group）"),
    PlotSpec("plsda", "plsda_plot", "PLS-DA", ("plsda_scores.csv",), "分组名（metadata Group）"),
    PlotSpec(
        "volcano",
        "volcano_plot",
        "Volcano Plot",
        ("volcano_results.csv",),
        "significant / nonsignificant",
    ),
    PlotSpec(
        "vip_bar",
        "vip_scores",
        "VIP Scores",
        ("vip_scores.csv",),
        "bar 主色 bar_color",
    ),
    PlotSpec(
        "heatmap_vip",
        "heatmap_top_vip",
        "Top VIP Heatmap",
        ("heatmap_top_vip_matrix.csv",),
        "热图色标",
    ),
    PlotSpec(
        "family_size",
        "family_size_distribution",
        "Molecular Family Size Distribution",
        ("network_nodes.csv",),
        "bar 类别名（分子家族名）",
    ),
    PlotSpec(
        "degree_hist",
        "degree_distribution",
        "Node Degree Distribution",
        ("network_nodes.csv",),
        "直方图主色 histogram_color",
    ),
    PlotSpec(
        "cosine_hist",
        "cosine_distribution",
        "Cosine Similarity Distribution",
        ("network_edges.csv",),
        "直方图主色 histogram_color",
    ),
    PlotSpec(
        "network_topology",
        "network_topology",
        "Molecular Network Topology",
        ("network_layout.csv",),
        "分子家族调色板",
    ),
    PlotSpec(
        "precursor_mass_diff",
        "precursor_mass_diff",
        "Precursor Mass Difference",
        ("network_nodes.csv", "network_edges.csv"),
        "histogram_color",
    ),
)

# 最长前缀优先匹配
_PLOT_SPECS_SORTED = tuple(sorted(PLOT_SPECS, key=lambda s: len(s.stem_prefix), reverse=True))

PLOT_ALIASES: dict[str, str] = {
    "pca": "pca_plot",
    "主成分": "pca_plot",
    "plsda": "plsda_plot",
    "pls-da": "plsda_plot",
    "火山": "volcano_plot",
    "volcano": "volcano_plot",
    "vip": "vip_scores",
    "vip得分": "vip_scores",
    "vip分数": "vip_scores",
    "vip热图": "heatmap_top_vip",
    "heatmap": "heatmap_top_vip",
    "热图": "heatmap_top_vip",
    "家族大小": "family_size_distribution",
    "family size": "family_size_distribution",
    "分子家族": "family_size_distribution",
    "度数分布": "degree_distribution",
    "degree": "degree_distribution",
    "余弦": "cosine_distribution",
    "cosine": "cosine_distribution",
    "相似度分布": "cosine_distribution",
    "余弦分布": "cosine_distribution",
    "gnps余弦": "cosine_distribution",
    "gnps 余弦": "cosine_distribution",
    "网络拓扑": "network_topology",
    "topology": "network_topology",
    "network topology": "network_topology",
    "pearson": "pearson_distribution",
    "皮尔逊": "pearson_distribution",
    "precursor": "precursor_mass_diff",
    "质量差": "precursor_mass_diff",
    "fbmn": "fbmn_group_intensity",
    "组强度": "fbmn_group_intensity",
    "mass2motif": "mass2motif_overview",
    "motif overview": "mass2motif_overview",
    "motif fragments": "mass2motif_fragments",
    "碎片": "mass2motif_fragments",
    "motif heatmap": "motif_spectrum_heatmap",
    "motif network": "mass2motif_network",
    "化学类别": "chemical_class_distribution",
    "chemical class": "chemical_class_distribution",
    "化学共识": "family_chemical_consensus",
    "注释传播": "annotation_propagation_summary",
    "annotation": "annotation_propagation_summary",
    "kegg": "kegg_compound_bubble",
    "气泡图": "kegg_compound_bubble",
}

# 已全部纳入语义 SVG；保留空集合便于兼容旧判断
UNSUPPORTED_EDIT_STEMS = frozenset()

# FBMN 子目录使用 fbmn_*.csv，与 GNPS 的 network_*.csv 同构
_NETWORK_DATA_ALIASES: dict[str, tuple[str, ...]] = {
    "network_nodes.csv": ("network_nodes.csv", "fbmn_nodes.csv"),
    "network_edges.csv": ("network_edges.csv", "fbmn_edges.csv"),
}


def resolve_plot_data_file(data_dir: Path, filename: str) -> Path | None:
    """在 data_dir 中解析语义数据文件（含 FBMN 别名）。"""
    root = Path(data_dir)
    for candidate in _NETWORK_DATA_ALIASES.get(filename, (filename,)):
        path = root / candidate
        if path.is_file():
            return path
    return None


def plot_data_files_ready(data_dir: Path, data_files: tuple[str, ...]) -> bool:
    return all(resolve_plot_data_file(data_dir, name) is not None for name in data_files)


# 常见分析结果图（即使暂无语义 CSV，也可走通用 Agent 改图）
GENERIC_AGENT_PLOT_STEMS = frozenset({
    "pearson_distribution",
    "fbmn_group_intensity",
    "mass2motif_overview",
    "mass2motif_fragments",
    "motif_spectrum_heatmap",
    "mass2motif_network",
    "chemical_class_distribution",
    "family_chemical_consensus",
    "annotation_propagation_summary",
    "kegg_compound_bubble",
    "kegg_compound_dotplot",
    "kegg_compound_barplot",
})


def plot_type_from_stem(stem: str) -> str | None:
    for spec in _PLOT_SPECS_SORTED:
        if stem == spec.stem_prefix or stem.startswith(f"{spec.stem_prefix}_"):
            return spec.plot_type
    return None


def stem_prefix_for_plot_type(plot_type: str) -> str | None:
    for spec in PLOT_SPECS:
        if spec.plot_type == plot_type:
            return spec.stem_prefix
    return None


def get_plot_spec(plot_type: str) -> PlotSpec | None:
    for spec in PLOT_SPECS:
        if spec.plot_type == plot_type:
            return spec
    return None


def agent_editable_stems() -> frozenset[str]:
    return frozenset(spec.stem_prefix for spec in PLOT_SPECS)


def is_agent_plot_editable_stem(stem: str) -> bool:
    """是否具备语义重绘能力（有 PlotSpec）。通用 PNG 改图不依赖此判断。"""
    if UNSUPPORTED_EDIT_STEMS and (
        stem in UNSUPPORTED_EDIT_STEMS or stem.startswith(tuple(UNSUPPORTED_EDIT_STEMS))
    ):
        return False
    return plot_type_from_stem(stem) is not None


def _png_stem(name: str) -> str:
    return Path(name).stem


def resolve_plot_source_rel(
    output_root: Path,
    source_rel: str | None = None,
    *,
    hint_message: str | None = None,
) -> str:
    """将 Agent/用户给出的路径规范化为 outputspace 内真实 PNG 相对路径。

    LLM 常只传 ``cosine_distribution.png``，实际文件可能在
    ``molecular_network_results/cosine_distribution.png``。
    """
    plots = list_editable_plots(output_root)
    if not plots:
        raise ValueError(
            "未找到可 Agent 改图的图片。请先完成分析生成结果图。"
        )

    rel = str(source_rel or "").strip().lstrip("/")
    if rel:
        candidate = (output_root / rel).resolve()
        try:
            candidate.relative_to(output_root.resolve())
            if candidate.is_file() and candidate.suffix.lower() == ".png":
                return Path(rel).as_posix()
        except ValueError:
            pass

        basename = Path(rel).name
        by_name = [item for item in plots if item["name"] == basename]
        if by_name:
            return by_name[0]["rel"]

        stem = _png_stem(basename)
        by_stem = [
            item
            for item in plots
            if item["stem"] == stem or item["stem"].startswith(f"{stem}_")
        ]
        if by_stem:
            return by_stem[0]["rel"]

        if rel in {item["rel"] for item in plots}:
            return rel

    hint = " ".join(part for part in (hint_message, source_rel) if part and str(part).strip())
    if hint.strip():
        target = resolve_plot_target(hint, plots)
        if target:
            return target

    label = rel or hint_message or "?"
    raise ValueError(f"无法在 output 目录中定位 PNG：{label}")


def list_editable_plots(output_root: Path) -> list[dict[str, Any]]:
    """扫描 outputspace 中可 Agent 改图的 PNG。

    - 语义图（有 PlotSpec + 数据 CSV）：edit_mode=semantic
    - 其余结果 PNG（含分子网络附加图）：edit_mode=generic
    同 stem 多目录只保留最新一份。
    """
    from web_frontend.backend.session_storage import MERGED_FIGURES_SUBDIR

    if not output_root.is_dir():
        return []
    found: list[dict[str, Any]] = []
    for png in sorted(output_root.rglob("*.png")):
        rel_parts = png.relative_to(output_root).parts
        if rel_parts and rel_parts[0] in {EDITED_PLOTS_SUBDIR, MERGED_FIGURES_SUBDIR}:
            continue
        stem = png.stem
        # 跳过明显中间产物命名
        if stem.endswith("_edited") or stem.startswith("tmp_"):
            continue
        rel = png.relative_to(output_root).as_posix()
        plot_type = plot_type_from_stem(stem)
        spec = get_plot_spec(plot_type or "") if plot_type else None
        edit_mode = "generic"
        title = stem.replace("_", " ")
        if spec and plot_data_files_ready(png.parent, spec.data_files):
            edit_mode = "semantic"
            title = spec.default_title
            plot_type = spec.plot_type
        elif plot_type:
            # 已注册但缺数据文件：仍可通用改标题
            edit_mode = "generic"
            title = spec.default_title if spec else title
        found.append(
            {
                "rel": rel,
                "name": png.name,
                "stem": stem,
                "plot_type": plot_type or "generic",
                "title": title,
                "edit_mode": edit_mode,
                "modified": png.stat().st_mtime,
            }
        )
    by_stem: dict[str, dict[str, Any]] = {}
    for item in found:
        prev = by_stem.get(item["stem"])
        if prev is None or item["modified"] >= prev["modified"]:
            by_stem[item["stem"]] = item
    deduped = list(by_stem.values())
    deduped.sort(key=lambda item: item["modified"], reverse=True)
    return deduped


_PLOT_EDIT_INTENT_RE = re.compile(
    r"(?:"
    r"改图|修改(?:一下)?图|调整(?:一下)?图|更改?图|美化图|"
    r"标题改|标题改为|标题改成|标题修改为|标题为|改(?:一下)?标题|修改.*标题|更换标题|"
    r"颜色|色号|配色|调色|字体|字号|图例|"
    r"用\s*#|#[0-9a-fA-F]{3,8}\b|"
    r"改成|改为|换成|用.{0,8}色|"
    r"直方图|分布图|拓扑图|热图|气泡图|"
    r"重新绘|重绘|重新作图|重新生成图|"
    r"edit\s+(?:the\s+)?plot|change\s+(?:the\s+)?title|recolor|font\s+size|plot\s+style"
    r")",
    re.IGNORECASE,
)

_PLOT_REFERENCE_RE = re.compile(
    r"(?:"
    r"pca|plsda|pls-da|主成分|火山|volcano|vip|热图|heatmap|"
    r"余弦|cosine|相似度|度数|分布图|拓扑|topology|"
    r"pearson|皮尔逊|fbmn|mass2motif|motif|化学类别|注释传播|kegg|气泡|"
    r"pca_plot|volcano_plot|cosine_distribution|degree_distribution|family_size|"
    r"network_topology|chemical_class|annotation_propagation|precursor_mass|"
    r"[\w.-]+\.png"
    r")",
    re.IGNORECASE,
)
_PLOT_STYLE_RE = re.compile(
    r"(?:标题|字号|字体|颜色|色号|配色|图例|改成|改为|换成|用\s*#|#[0-9a-fA-F]{3,8})",
    re.IGNORECASE,
)


def looks_like_plot_edit_request(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False

    # 全流程分析请求（如「对 raw 进行分析包括 xcms 和分子网络」）不是改图
    if re.search(r"(?:进行|执行|跑|开始|继续).{0,12}分析", text):
        if not re.search(r"标题|颜色|色号|配色|#|改成|改为|改图|字号|字体|直方图|分布图", text):
            return False

    if _PLOT_EDIT_INTENT_RE.search(text):
        return True
    if _PLOT_REFERENCE_RE.search(text) and _PLOT_STYLE_RE.search(text):
        return True
    return False


def should_route_plot_edit(message: str) -> bool:
    """是否应走改图 SSE（比 looks_like 略宽，支持多行拆分）。"""
    if looks_like_plot_edit_request(message):
        return True
    lines = split_plot_edit_lines(message)
    return len(lines) > 0


def split_plot_edit_lines(message: str) -> list[str]:
    """将一条消息拆成多条改图指令（按换行）。"""
    text = (message or "").strip()
    if not text:
        return []
    parts = re.split(r"\n+", text)
    lines: list[str] = []
    for part in parts:
        line = re.sub(r"^\s*\d+[.、)\]]\s*", "", part.strip())
        if line:
            lines.append(line)
    if len(lines) <= 1:
        return [text] if looks_like_plot_edit_request(text) else []
    return [line for line in lines if looks_like_plot_edit_request(line)]


def _alias_stem_from_message(message: str) -> str | None:
    lower = message.lower()
    for alias, stem in sorted(PLOT_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if alias in lower or alias in message:
            return stem
    return None


def resolve_plot_target(message: str, plots: list[dict[str, Any]]) -> str | None:
    """从用户消息与可用图中解析 source_rel。"""
    if not plots:
        return None

    alias_stem = _alias_stem_from_message(message)
    if alias_stem:
        if alias_stem in UNSUPPORTED_EDIT_STEMS:
            return None
        for item in plots:
            if item["stem"] == alias_stem or item["stem"].startswith(f"{alias_stem}_"):
                return item["rel"]
        for item in plots:
            if alias_stem.replace("_", "") in item["stem"].replace("_", ""):
                return item["rel"]

    # 消息里直接写了文件名
    for item in plots:
        if item["name"] in message or item["rel"] in message:
            return item["rel"]

    # 仅一张可改图时默认选它
    if len(plots) == 1:
        return plots[0]["rel"]

    # 多张图：按 plot_type / 别名关键词打分
    lower = message.lower()
    best_rel = None
    best_score = -1
    alias_stem = _alias_stem_from_message(message)
    for item in plots:
        score = 0
        stem = item["stem"]
        ptype = item.get("plot_type") or ""
        if alias_stem and (item["stem"] == alias_stem or item["stem"].startswith(f"{alias_stem}_")):
            score += 10
        if ptype and ptype in lower:
            score += 3
        if "pca" in lower and "pca" in stem:
            score += 5
        if ("火山" in message or "volcano" in lower) and "volcano" in stem:
            score += 5
        if ("余弦" in message or "cosine" in lower) and "cosine" in stem:
            score += 5
        if stem.replace("_", "") in lower.replace("_", "").replace(" ", ""):
            score += 2
        if score > best_score:
            best_score = score
            best_rel = item["rel"]
    if best_score > 0:
        return best_rel

    return plots[0]["rel"]


def extract_plot_edit_tasks(
    message: str,
    plots: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    """解析为 (source_rel, instruction) 列表，支持一条消息改多张图。"""
    if not plots:
        return []
    lines = split_plot_edit_lines(message)
    if not lines:
        if not looks_like_plot_edit_request(message):
            return []
        lines = [message]

    tasks: list[tuple[str, str]] = []
    for line in lines:
        rel = resolve_plot_target(line, plots)
        if rel:
            tasks.append((rel, line))
    return tasks
