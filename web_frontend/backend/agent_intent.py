"""判断用户消息是否应走 Agent（工具执行）而非纯 LLM 对话。"""
from __future__ import annotations

import re

from web_frontend.backend.image_merge_registry import (
    looks_like_image_merge_request,
    looks_like_merged_figure_edit_request,
)
from web_frontend.backend.plot_edit_registry import looks_like_plot_edit_request

ATTACHMENT_MARKERS = ("[已上传附件]", "[Attachments uploaded]")

# 与 web_frontend/static/app.js 中 shouldUseAgent 保持语义一致
ANALYSIS_INTENT_RE = re.compile(
    r"(?:"
    r"继续|重新(?:运行|进行|分析|做)|执行分析|跑一遍|开始分析|运行工具|"
    r"分子网(?:络|格)|molecular\s*network|GNPS|DeepMASS|deepmass|"
    r"XCMS|峰检测|差异代谢|谱库注释|富集分析|"
    # 统计 / 火山 / mixOmics（避免「做统计，火山图对比…」落入纯对话幻觉）
    r"统计(?:分析)?|做统计|跑统计|统计作图|mixOmics|mixomics|"
    r"火山图|volcano\s*plot|volcano|"
    r"PLS-?DA|做\s*PCA|跑\s*PCA|"
    r"组间对比|两组对比|显著性分析|差异分析|"
    r"Treatment\s*vs\.?\s*Control|Control\s*vs\.?\s*Treatment|"
    r"(?:Treatment|Control|Group).{0,20}(?:vs|VS|对比|比较)|"
    r"converted_mzml|spectra\.mgf|\.mzML|\.mgf|"
    r"continue|re-?run|run analysis|start agent|execute pipeline"
    r")",
    re.IGNORECASE,
)


def looks_like_agent_request(user_message: str) -> bool:
    """分析 / 改图 / 拼图 均走统一 Agent loop（由 LLM 选工具）。"""
    text = (user_message or "").strip()
    if not text:
        return False
    # 改图、拼图、改拼图：统一进 Agent，由 plot_edit / image_merge / merge_edit 执行
    if looks_like_plot_edit_request(text):
        return True
    if looks_like_image_merge_request(text) or looks_like_merged_figure_edit_request(text):
        return True
    if any(marker in text for marker in ATTACHMENT_MARKERS):
        return True
    return bool(ANALYSIS_INTENT_RE.search(text))
