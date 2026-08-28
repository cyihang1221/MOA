"""多模态读图：Vision LLM 描述 PNG 可见模式（Package C）。"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from web_frontend.backend.json_parse import extract_first_json_object

_VISION_SYSTEM = """你是代谢组学/质谱科研图表解读助手。用户会提供一张已生成的统计图 PNG 及辅助文字。
请**只描述图中可见的视觉模式**，不要编造图中没有的文字、数值或显著性结论。

输出 JSON（不要 markdown）：
{
  "visible_patterns": ["要点1", "要点2"],
  "group_separation": "若适用：组间是否在得分轴/颜色上可区分；不适用则写 N/A",
  "notable_features": "轴标签、图例、阈值线、标注点等可见元素",
  "interpretation_boundary": "哪些结论不能仅从本图断定（1 句）",
  "confidence": 0.0
}
confidence 0~1：图像清晰且模式明确则高；模糊或无法判断则低。
"""

_MAX_BYTES = 4 * 1024 * 1024


def vision_enabled() -> bool:
    v = os.getenv("MASSAGENT_FIGURE_VISION", "1").strip().lower()
    return v not in {"0", "false", "off", "no"}


def _vision_model() -> str | None:
    m = os.getenv("MASSAGENT_VISION_MODEL", "").strip()
    return m or None


def _encode_png(path: Path) -> str | None:
    if not path.is_file():
        return None
    data = path.read_bytes()
    if len(data) > _MAX_BYTES:
        return None
    return base64.standard_b64encode(data).decode("ascii")


def describe_figure_image(
    png_path: str | Path,
    *,
    plot_type: str = "",
    objective: str = "",
    data_narrative: dict[str, Any] | None = None,
    caption_excerpt: str = "",
    llm_client: Any | None = None,
) -> dict[str, Any]:
    """调用 Vision-capable LLM 读图；失败时返回 error 字段。"""
    path = Path(png_path)
    if not vision_enabled():
        return {"skipped": True, "reason": "MASSAGENT_FIGURE_VISION=0"}
    b64 = _encode_png(path)
    if not b64:
        return {"skipped": True, "reason": "图片不存在或超过 4MB"}

    bullets = (data_narrative or {}).get("bullets") or []
    user_text = (
        f"plot_type={plot_type}\n"
        f"分析目标摘录：{(objective or '')[:400]}\n"
        f"图注摘录：{(caption_excerpt or '')[:400]}\n"
        f"CSV 数据支撑：{'；'.join(str(b) for b in bullets[:5]) or '无'}\n"
        "请根据图像内容输出 JSON。"
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _VISION_SYSTEM},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                },
            ],
        },
    ]
    try:
        if llm_client is None:
            from web_frontend.backend.web_llm import WebLLMClient

            llm_client = WebLLMClient(model=_vision_model())
        raw = llm_client.think_complete(messages, temperature=0, max_tokens=2048)
        parsed = extract_first_json_object(str(raw or ""))
        if not parsed:
            return {"error": "Vision LLM 未返回有效 JSON", "raw": (raw or "")[:500]}
        parsed["source"] = "vision_llm"
        return parsed
    except Exception as exc:
        return {"error": str(exc), "source": "vision_llm"}


def format_vision_markdown(obs: dict[str, Any] | None, *, zh: bool = True) -> str:
    if not obs or obs.get("skipped") or obs.get("error"):
        return ""
    patterns = obs.get("visible_patterns") or []
    if not patterns and not obs.get("group_separation"):
        return ""
    head = "#### 读图观察（AI，供参考）\n\n" if zh else "#### Visual observation (AI)\n\n"
    lines = [head]
    for p in patterns:
        if str(p).strip():
            lines.append(f"- {p}")
    gs = str(obs.get("group_separation") or "").strip()
    if gs and gs.upper() != "N/A":
        lines.append(f"- **组间/分组模式**：{gs}")
    nf = str(obs.get("notable_features") or "").strip()
    if nf:
        lines.append(f"- **可见要素**：{nf}")
    boundary = str(obs.get("interpretation_boundary") or "").strip()
    if boundary:
        lines.append(f"- *解读边界*：{boundary}")
    return "\n".join(lines) + "\n"


def attach_vision_to_figures(
    figures: list[dict[str, Any]],
    *,
    objective: str = "",
    llm_client: Any | None = None,
    max_figures: int = 6,
) -> None:
    """就地写入 figure['vision_observation']（仅 rendered/copied_existing）。"""
    if not vision_enabled():
        return
    n = 0
    for fig in figures:
        if n >= max_figures:
            break
        if fig.get("status") not in {"rendered", "copied_existing"}:
            continue
        png = fig.get("png")
        if not png:
            continue
        fig["vision_observation"] = describe_figure_image(
            png,
            plot_type=str(fig.get("plot_type") or ""),
            objective=objective,
            data_narrative=fig.get("data_narrative"),
            caption_excerpt=str(fig.get("caption") or "")[:400],
            llm_client=llm_client,
        )
        n += 1


__all__ = [
    "attach_vision_to_figures",
    "describe_figure_image",
    "format_vision_markdown",
    "vision_enabled",
]
