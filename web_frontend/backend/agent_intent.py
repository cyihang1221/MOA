"""前端聊天意图：C（出图/改图/报告）vs B（分析计算，前端不执行）。"""
from __future__ import annotations

import re
from typing import Literal

from web_frontend.backend.image_merge_registry import (
    looks_like_image_merge_request,
    looks_like_merged_figure_edit_request,
)
from web_frontend.backend.plot_edit_registry import looks_like_plot_edit_request

ATTACHMENT_MARKERS = ("[已上传附件]", "[Attachments uploaded]")

FrontendIntent = Literal["c_visual", "c_report", "c_from_results", "b_analysis", "chat"]


def intent_text(user_message: str) -> str:
    """去掉前端自动拼接的附件清单，避免 .raw 等文件名被当成分析意图。"""
    text = (user_message or "").strip()
    for marker in ATTACHMENT_MARKERS:
        idx = text.find(marker)
        if idx >= 0:
            return text[:idx].rstrip()
    return text


# 明确是计算/预处理，应由 B 执行
B_COMPUTE_RE = re.compile(
    r"(?:"
    r"开始分析|执行分析|进行分析|做分析|跑一遍|运行工具|execute pipeline|run analysis|start agent|"
    r"重新(?:运行|进行|分析|做)|重跑|再来一遍|re-?run|"
    r"峰检测|预处理|gap[\s-]?fill|补峰|"
    r"XCMS|OpenMS|MZmine|MS-?DIAL|KPIC|PeakOnly|PITracer|TracMass|"
    r"convert(?:ed)?_mzml|ThermoRaw|msconvert|\.raw\b|"
    r"DeepMASS|deepmass|谱库注释|谱库匹配|"
    r"feature[_\s-]?filter|缺失值|"
    r"molecular_networking_|data_preprocessing_"
    r")",
    re.IGNORECASE,
)

# 会话已完成后的明确「重跑分析」
B_RERUN_RE = re.compile(
    r"(?:"
    r"重新(?:运行|进行|分析|做)|重跑(?:一遍|分析)?|再来一遍|"
    r"re-?run(?:\s+analysis)?|run\s+again"
    r")",
    re.IGNORECASE,
)

# 出图 / 写报告（C）
C_REPORT_RE = re.compile(
    r"(?:"
    r"写(?:一份|篇)?(?:深度)?报告|写深度报告|深度报告|深度解读|"
    r"生成(?:深度)?报告|分析报告|final_report|"
    r"科研意义|分析价值|价值与意义|分析意义|写解读|"
    r"按方案出图|出图|可视化|科研图表|figure\s*list|"
    r"interpretation|图注|caption|insight\s*report"
    r")",
    re.IGNORECASE,
)

# 话术像分析，但也可能只是要已有结果的图
C_FROM_RESULTS_RE = re.compile(
    r"(?:"
    r"统计(?:分析|作图)?|做统计|跑统计|mixOmics|mixomics|"
    r"火山图|volcano|"
    r"PLS-?DA|做\s*PCA|跑\s*PCA|(?<![a-z])pca(?![a-z])|主成分|"
    r"组间对比|两组对比|显著性分析|差异分析|"
    r"分子网(?:络|格)|molecular\s*network|GNPS|FBMN|"
    r"富集分析|KEGG|"
    r"Treatment\s*vs\.?\s*Control|Control\s*vs\.?\s*Treatment|"
    r"(?:Treatment|Control|Group).{0,20}(?:vs|VS|对比|比较)"
    r")",
    re.IGNORECASE,
)


def looks_like_c_visual_request(user_message: str) -> bool:
    text = intent_text(user_message)
    if not text:
        return False
    return (
        looks_like_plot_edit_request(text)
        or looks_like_image_merge_request(text)
        or looks_like_merged_figure_edit_request(text)
    )


def classify_frontend_intent(user_message: str) -> FrontendIntent:
    """前端只做 C：改图/拼图/出报告；计算类话术标为 b_analysis 供交接，不调 MCP。"""
    text = intent_text(user_message)
    if not text:
        return "chat"
    if looks_like_c_visual_request(text):
        return "c_visual"
    if C_REPORT_RE.search(text):
        return "c_report"
    compute = bool(B_COMPUTE_RE.search(text))
    rerun = bool(B_RERUN_RE.search(text))
    from_results = bool(C_FROM_RESULTS_RE.search(text))
    # 计算/重跑优先于「像分析的话术」；避免 COMPLETED 下误进 C 写报告
    if compute or rerun:
        return "b_analysis"
    if from_results:
        return "c_from_results"
    return "chat"


def looks_like_agent_request(user_message: str) -> bool:
    """C 能力或需要向 B 交接的分析话术，都进前端 Agent（后者只说明不执行）。"""
    if not intent_text(user_message):
        return False
    if classify_frontend_intent(user_message) != "chat":
        return True
    return bool(
        re.search(
            r"确认计划|批准执行|按此执行|confirm(?:\s+the)?\s+plan",
            intent_text(user_message),
            re.IGNORECASE,
        )
    )
