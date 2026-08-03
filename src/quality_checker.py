"""
V3.0 质量检查器 — 从工具执行结果中提取关键指标，
辅助 LLM 进行质量判断。
"""

import re
import os
import json


def parse_tool_result(tool_name, result_text):
    """
    从工具返回的字符串中提取结构化信息。

    MCP 工具的返回格式通常为：
    "已使用 <tool_name> 完成 <task>. 输出: <output_info>"

    Returns:
        dict with keys: tool_name, raw_result, output_paths, file_count
    """
    info = {
        "tool_name": tool_name,
        "raw_result": str(result_text),
        "output_paths": _extract_paths(str(result_text)),
        "key_numbers": _extract_numbers(str(result_text)),
    }
    return info


def _extract_paths(text):
    """从文本中提取文件路径。"""
    paths = []
    # 匹配常见路径模式
    patterns = [
        r'/[^\s,;]*\.(?:csv|mgf|mzML|mzXML|rds|featureXML|graphml|png|txt|tsv)',
        r'output_dir:\s*(\S+)',
        r'output[^:]*:\s*(\S+)',
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        paths.extend(matches)
    return list(set(paths))


def _extract_numbers(text):
    """从文本中尝试提取关键数值指标。"""
    numbers = {}
    patterns = {
        "features": r'(\d+)\s*features?',
        "compounds": r'(\d+)\s*compounds?',
        "metabolites": r'(\d+)\s*metabolites?',
        "samples": r'(\d+)\s*samples?',
        "spectra": r'(\d+)\s*spectra?',
        "clusters": r'(\d+)\s*clusters?',
        "families": r'(\d+)\s*(?:molecular\s*)?famil(?:y|ies)',
        "pathways": r'(\d+)\s*pathways?',
        "edges": r'(\d+)\s*edges?',
        "nodes": r'(\d+)\s*nodes?',
    }
    for key, pat in patterns.items():
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            numbers[key] = int(match.group(1))
    return numbers


def check_output_files_exist(output_dir, expected_patterns=None):
    """
    检查输出目录中是否存在预期的输出文件。

    Args:
        output_dir: 输出目录路径
        expected_patterns: 预期文件名模式列表，如 ['*.csv', '*.mgf']

    Returns:
        dict: {pattern: [matching_files]}
    """
    if not output_dir or not os.path.isdir(output_dir):
        return {"error": f"Output directory does not exist: {output_dir}"}

    result = {}
    if expected_patterns:
        import glob
        for pattern in expected_patterns:
            matches = glob.glob(os.path.join(output_dir, pattern))
            result[pattern] = matches
    else:
        # 列出所有文件
        files = []
        for root, dirs, filenames in os.walk(output_dir):
            for f in filenames:
                files.append(os.path.join(root, f))
        result["all_files"] = files[:50]  # 限制数量

    return result


def extract_quality_info_from_history(history_summary):
    """
    从完整的历史摘要中提取质量相关的信息，
    用于报告生成。
    """
    quality_summary = []
    for entry in history_summary:
        if isinstance(entry, dict) and entry.get("role") == "tool":
            content = entry.get("content", "")
            # 标记质量检查相关的条目
            if "quality" in content.lower() or "check" in content.lower():
                quality_summary.append(content)
    return quality_summary
