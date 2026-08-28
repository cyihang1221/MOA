"""Agent：将自然语言改图要求解析为 plot_config patch。"""
from __future__ import annotations

import json
import re
from typing import Any

from web_frontend.backend.analysis_intent import (
    intent_to_plot_patch,
    merge_intent_into_patch,
    parse_analysis_intent,
)
from web_frontend.backend.anti_hallucination import (
    PLOT_EDIT_SYSTEM_GUARD,
    messages_with_system,
)
from web_frontend.backend.json_parse import extract_first_json_object
from web_frontend.backend.plot_edit_registry import get_plot_spec
from web_frontend.backend.plot_theme import sanitize_volcano_plot_patch
from web_frontend.backend.web_llm import WebLLMClient

_SCHEMA_BY_CATEGORY = {
    "scores": """{{
  "title": "新标题（可选）",
  "color_by": "metadata 列名，如 Group / Batch / Time（换着色维度时必填）",
  "color_type": "nominal 或 quantitative（可省略，由列类型推断）",
  "cluster": {{"method": "kmeans", "n": 3}} 或 null,
  "palette": {{"分组名": "#RRGGBB"}},
  "font_size": {{"title": 18, "axis": 12, "legend": 11, "label": 10}},
  "figure_size": [10, 8],
  "components": [1, 2],
  "show_sample_labels": true,
  "axes": {{"x_title": "", "y_title": "", "x_min": null, "x_max": null, "y_min": null, "y_max": null}},
  "legend": {{"show": true, "position": "right"}},
  "marks": {{"size": 70, "opacity": 0.85}},
  "title_align": "left|center|right"
}}""",
    "volcano": """{{
  "title": "新标题（可选）",
  "colors": {{
    "upregulated": "#E64B35",
    "downregulated": "#4DBBD5",
    "nonsignificant": "#B0B0B0",
    "threshold_color": "#d62728"
  }},
  "font_size": {{"title": 18, "axis": 12, "legend": 11}},
  "figure_size": [8, 6],
  "axes": {{"x_title": "", "y_title": "", "x_min": null, "x_max": null, "y_min": null, "y_max": null}},
  "legend": {{"show": true, "position": "right"}},
  "marks": {{"size": 70, "opacity": 0.85}},
  "title_align": "left|center|right"
}}""",
    "bar": """{{
  "title": "新标题（可选）",
  "palette": {{"类别名": "#RRGGBB"}},
  "font_size": {{"title": 16, "axis": 12, "label": 9}},
  "figure_size": [10, 5],
  "axes": {{"x_title": "", "y_title": "", "y_min": null, "y_max": null}},
  "marks": {{"opacity": 0.85}},
  "title_align": "left|center|right"
}}""",
    "hist": """{{
  "title": "新标题（可选）",
  "colors": {{"histogram_color": "#4c72b0", "threshold_color": "#d62728", "median_color": "#ff7f0e"}},
  "font_size": {{"title": 16, "axis": 12, "legend": 10}},
  "figure_size": [8, 5],
  "axes": {{"x_title": "", "y_title": "", "x_min": null, "x_max": null, "y_min": null, "y_max": null}},
  "marks": {{"opacity": 0.85}},
  "histogram": {{"bins": 40}},
  "title_align": "left|center|right"
}}""",
}


def _category_for_plot_type(plot_type: str) -> str:
    if plot_type in ("pca", "plsda"):
        return "scores"
    if plot_type == "volcano":
        return "volcano"
    if plot_type in ("family_size", "vip_bar"):
        return "bar"
    if plot_type in ("heatmap_vip", "network_topology"):
        return "bar"
    return "hist"


def _build_prompt(
    *,
    plot_type: str,
    color_keys: list[str],
    current_config: dict[str, Any],
    instruction: str,
    metadata_columns: list[str] | None = None,
    literature_context: str | None = None,
) -> str:
    spec = get_plot_spec(plot_type)
    plot_label = spec.default_title if spec else plot_type
    category = _category_for_plot_type(plot_type)
    schema = _SCHEMA_BY_CATEGORY[category]
    keys_hint = spec.color_keys_hint if spec else "颜色键"
    meta_hint = ""
    if plot_type in {"pca", "plsda"}:
        cols = metadata_columns or []
        meta_hint = f"""
可用 metadata 着色列：{json.dumps(cols, ensure_ascii=False)}
当前 color_by：{json.dumps(current_config.get("color_by"), ensure_ascii=False)}
若用户要求「按某列/时间/Batch/聚类着色」，必须设置 color_by 或 cluster，禁止只改 palette 假装换了着色维度。
按聚类着色示例：{{"cluster": {{"method": "kmeans", "n": 3}}}}
"""
    elif plot_type == "volcano":
        meta_hint = """
火山图规范：
- 禁止 color_by / palette / cluster（火山按上/下调/不显著三色着色）
- 不要删除或清空 thresholds；默认 p=0.05、|log2FC|>=1，阈值线由系统绘制
- 文献配色只改 colors.upregulated / downregulated / nonsignificant / threshold_color
"""
    lit_hint = ""
    if (literature_context or "").strip():
        lit_hint = f"""
文献作图参考（来自已匹配 Skill，优先级低于用户明确要求；不得编造文献未提及的数据列或阈值）：
{(literature_context or "").strip()}
"""
    return f"""你是代谢组学作图助手。用户要修改一张「{plot_label}」图（类型: {plot_type}）。
{lit_hint}
当前配置：
{json.dumps(current_config, ensure_ascii=False, indent=2)}

可用颜色键说明：{keys_hint}
当前可用键：{json.dumps(color_keys, ensure_ascii=False)}
{meta_hint}
用户要求：
{instruction.strip()}

请只输出一个 JSON 对象，包含需要修改的字段（未提及的不要输出）：
{schema}

规则：
- 颜色用十六进制 #RRGGBB
- palette / colors 的键使用英文或数据中已有的类别名
- 标题靠左/居中/靠右分别用 title_align: left / center / right
- 减小或增大标题字号时修改 font_size.title；「放大/缩小 N 个字号」必须基于当前 font_size.title 做加减，输出最终绝对值
- 只改字号时不要改 title；必须保留当前配置中的标题原文
- 换着色字段用 color_by（metadata 列名）；聚类用 cluster；不要用改 palette 键名冒充换维度
- 不要编造不存在的颜色键、metadata 列或文件路径
- 不要输出「已保存」「已改好」等完成声明
- 不要输出 markdown 或解释文字
- 若文献参考与用户指令冲突，以用户指令为准
"""


def _current_title_font_size(current_config: dict[str, Any]) -> int:
    font = current_config.get("font_size") if isinstance(current_config, dict) else None
    if isinstance(font, dict):
        try:
            return max(8, min(96, int(font.get("title") or 16)))
        except (TypeError, ValueError):
            pass
    return 16


def _heuristic_font_size_patch(
    instruction: str,
    current_config: dict[str, Any],
) -> dict[str, Any] | None:
    """解析「标题放大/缩小 N 个字号」等，避免连续改图时丢掉标题或算错字号。"""
    text = (instruction or "").strip()
    if not text:
        return None
    cur = _current_title_font_size(current_config)

    m = re.search(
        r"(?:标题)?(?:的)?(?:字号|字体大小|字体)?(?:再)?(?:放大|增大|增加|加大|加)\s*(\d+)\s*(?:个)?(?:字号|磅|pt)?",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        return {"font_size": {"title": min(72, cur + int(m.group(1)))}}

    m = re.search(
        r"(?:标题)?(?:的)?(?:字号|字体大小|字体)?(?:再)?(?:缩小|减小|减少|减)\s*(\d+)\s*(?:个)?(?:字号|磅|pt)?",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        return {"font_size": {"title": max(8, cur - int(m.group(1)))}}

    m = re.search(
        r"(?:标题)?(?:字号|字体大小|字体)\s*(?:改成|改为|设为|设置成|设置为|调到|调成|=|:|：)\s*(\d+)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        return {"font_size": {"title": max(8, min(72, int(m.group(1))))}}

    m = re.search(
        r"(?:enlarge|increase|increase\s+by|grow)\s+(?:the\s+)?(?:title\s+)?(?:font\s*size\s+)?(?:by\s+)?(\d+)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        return {"font_size": {"title": min(72, cur + int(m.group(1)))}}

    return None


def _heuristic_title_patch(instruction: str) -> dict[str, Any] | None:
    text = (instruction or "").strip()
    if not text:
        return None
    patterns = [
        r"(?:把|将)?标题(?:改成|改为|修改为|设为|换成)\s*[「『\"“](.+?)[」』\"”]\s*$",
        r"(?:把|将)?标题(?:改成|改为|修改为|设为|换成)\s*[「『\"']?(.+?)[」』\"']?\s*$",
        r"(?:change|set)\s+(?:the\s+)?title\s+to\s+[\"']?(.+?)[\"']?\s*$",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            title = m.group(1).strip().rstrip("。．.！!")
            if title and "字号" not in title and "放大" not in title:
                return {"title": title}
    return None


def parse_plot_edit_instruction(
    *,
    instruction: str,
    plot_type: str,
    color_keys: list[str],
    current_config: dict[str, Any],
    model: str | None = None,
    metadata_columns: list[str] | None = None,
    literature_context: str | None = None,
) -> dict[str, Any]:
    if not instruction.strip():
        raise ValueError("改图说明不能为空")

    intent = parse_analysis_intent(
        instruction,
        plot_type=plot_type,
        metadata_columns=metadata_columns,
    )
    if intent.get("errors"):
        raise ValueError("；".join(str(e) for e in intent["errors"]))

    # 纯样式增量（字号+/-）优先走规则，避免 LLM 回写旧标题
    font_patch = _heuristic_font_size_patch(instruction, current_config)
    title_patch = _heuristic_title_patch(instruction)
    if font_patch and not title_patch and re.search(
        r"字号|字体|放大|缩小|enlarge|font\s*size", instruction, flags=re.IGNORECASE
    ):
        # 「只改字号」且能规则解析时，不再问 LLM，保留当前 title
        return font_patch

    llm = WebLLMClient(model=model)
    prompt = _build_prompt(
        plot_type=plot_type,
        color_keys=color_keys,
        current_config=current_config,
        instruction=instruction,
        metadata_columns=metadata_columns,
        literature_context=literature_context,
    )
    raw = llm.think_complete(
        messages_with_system(PLOT_EDIT_SYSTEM_GUARD, prompt),
        temperature=0.0,
        max_tokens=2048,
    )
    if not raw:
        # 规则意图足够时允许无 LLM
        patch: dict[str, Any] = {}
        if intent:
            patch = intent_to_plot_patch(intent)
        if title_patch:
            patch.update(title_patch)
        if font_patch:
            patch.setdefault("font_size", {}).update(font_patch.get("font_size") or {})
            patch["font_size"] = {
                **(patch.get("font_size") or {}),
                **(font_patch.get("font_size") or {}),
            }
        if patch:
            return patch
        raise RuntimeError("LLM 未返回有效内容，请检查 API 配置")

    patch = extract_first_json_object(raw)
    if not patch:
        if intent:
            patch = intent_to_plot_patch(intent)
        else:
            raise RuntimeError(f"无法解析 Agent 返回的 plot_config：{raw[:500]}")

    patch = merge_intent_into_patch(patch, intent)

    # 只改字号时：丢掉 LLM 可能编造/回退的 title，强制用规则字号
    if font_patch and not title_patch:
        patch.pop("title", None)
        fs = dict(patch.get("font_size") or {}) if isinstance(patch.get("font_size"), dict) else {}
        fs.update(font_patch.get("font_size") or {})
        patch["font_size"] = fs
    elif title_patch and "title" not in patch:
        patch["title"] = title_patch["title"]

    # 不再无条件注入 title：未改标题时由 merge_plot_config 保留上一版
    if plot_type == "volcano":
        patch = sanitize_volcano_plot_patch(patch)
    return patch
