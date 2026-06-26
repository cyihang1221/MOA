"""判断用户消息是否应走 Agent（MCP 工具）而非纯 LLM 对话。"""
from __future__ import annotations

import re

ATTACHMENT_MARKERS = ("[已上传附件]", "[Attachments uploaded]")

# 与 web_frontend/static/app.js 中 shouldUseAgent 保持语义一致
ANALYSIS_INTENT_RE = re.compile(
    r"(?:"
    r"继续|重新(?:运行|进行|分析|做)|执行分析|跑一遍|开始分析|运行工具|"
    r"分子网(?:络|格)|molecular\s*network|GNPS|DeepMASS|deepmass|"
    r"XCMS|峰检测|差异代谢|谱库注释|富集分析|"
    r"converted_mzml|spectra\.mgf|\.mzML|\.mgf|"
    r"continue|re-?run|run analysis|start agent|execute pipeline"
    r")",
    re.IGNORECASE,
)


def looks_like_agent_request(user_message: str) -> bool:
    text = (user_message or "").strip()
    if not text:
        return False
    if any(marker in text for marker in ATTACHMENT_MARKERS):
        return True
    return bool(ANALYSIS_INTENT_RE.search(text))
