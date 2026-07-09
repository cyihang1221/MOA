"""Agent：将自然语言改图要求解析为 plot_config patch。"""
from __future__ import annotations

import json
from typing import Any

from web_frontend.backend.json_parse import extract_first_json_object
from web_frontend.backend.plot_edit_registry import get_plot_spec
from web_frontend.backend.plot_theme import default_title
from web_frontend.backend.web_llm import WebLLMClient

_SCHEMA_BY_CATEGORY = {
    "scores": """{{
  "title": "新标题（可选）",
  "palette": {{"分组名": "#RRGGBB"}},
  "font_size": {{"title": 18, "axis": 12, "legend": 11, "label": 10}},
  "figure_size": [10, 8],
  "components": [1, 2],
  "show_sample_labels": true
}}""",
    "volcano": """{{
  "title": "新标题（可选）",
  "colors": {{"significant": "#E64B35", "nonsignificant": "#B0B0B0"}},
  "font_size": {{"title": 18, "axis": 12, "legend": 11}},
  "figure_size": [8, 6]
}}""",
    "bar": """{{
  "title": "新标题（可选）",
  "palette": {{"类别名": "#RRGGBB"}},
  "font_size": {{"title": 16, "axis": 12, "label": 9}},
  "figure_size": [10, 5]
}}""",
    "hist": """{{
  "title": "新标题（可选）",
  "colors": {{"histogram_color": "#4c72b0", "threshold_color": "#d62728", "median_color": "#ff7f0e"}},
  "font_size": {{"title": 16, "axis": 12, "legend": 10}},
  "figure_size": [8, 5]
}}""",
}


def _category_for_plot_type(plot_type: str) -> str:
    if plot_type in ("pca", "plsda"):
        return "scores"
    if plot_type == "volcano":
        return "volcano"
    if plot_type == "family_size":
        return "bar"
    return "hist"


def _build_prompt(
    *,
    plot_type: str,
    color_keys: list[str],
    current_config: dict[str, Any],
    instruction: str,
) -> str:
    spec = get_plot_spec(plot_type)
    plot_label = spec.default_title if spec else plot_type
    category = _category_for_plot_type(plot_type)
    schema = _SCHEMA_BY_CATEGORY[category]
    keys_hint = spec.color_keys_hint if spec else "颜色键"
    return f"""你是代谢组学作图助手。用户要修改一张「{plot_label}」图（类型: {plot_type}）。

当前配置：
{json.dumps(current_config, ensure_ascii=False, indent=2)}

可用颜色键说明：{keys_hint}
当前可用键：{json.dumps(color_keys, ensure_ascii=False)}

用户要求：
{instruction.strip()}

请只输出一个 JSON 对象，包含需要修改的字段（未提及的不要输出）：
{schema}

规则：
- 颜色用十六进制 #RRGGBB
- palette / colors 的键使用英文或数据中已有的类别名
- 不要输出 markdown 或解释文字
"""


def parse_plot_edit_instruction(
    *,
    instruction: str,
    plot_type: str,
    color_keys: list[str],
    current_config: dict[str, Any],
    model: str | None = None,
) -> dict[str, Any]:
    if not instruction.strip():
        raise ValueError("改图说明不能为空")

    llm = WebLLMClient(model=model)
    prompt = _build_prompt(
        plot_type=plot_type,
        color_keys=color_keys,
        current_config=current_config,
        instruction=instruction,
    )
    raw = llm.think_complete([{"role": "user", "content": prompt}], temperature=0.0, max_tokens=2048)
    if not raw:
        raise RuntimeError("LLM 未返回有效内容，请检查 API 配置")

    patch = extract_first_json_object(raw)
    if not patch:
        raise RuntimeError(f"无法解析 Agent 返回的 plot_config：{raw[:500]}")

    if "title" not in patch:
        patch.setdefault("title", current_config.get("title") or default_title(plot_type))
    return patch
