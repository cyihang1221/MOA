"""定位 Agent B 要消费的 MassOmics PlanDocument。"""
from __future__ import annotations

import json
from pathlib import Path


def _is_plan_document(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and "goal" in data and isinstance(data.get("steps"), list)


def find_massomics_plan_json(
    output_dir: str | Path,
    upload_dir: str | Path | None = None,
) -> Path | None:
    """在会话输出/上传目录找最新的 ``plan_*.json``（不含 Agent B 自己写的适配稿）。"""
    folders: list[Path] = [Path(output_dir)]
    if upload_dir:
        folders.append(Path(upload_dir))
    hits: list[Path] = []
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in folder.glob("plan_*.json"):
            name = path.name.lower()
            if name.startswith("plan_b_") or "adapted" in name:
                continue
            if _is_plan_document(path):
                hits.append(path)
        if hits:
            break
    if not hits:
        return None
    hits.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    return hits[0]


def load_plan_document(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"计划必须是 JSON 对象: {path}")
    if "goal" not in data or not isinstance(data.get("steps"), list):
        raise ValueError(f"不是 MassOmics PlanDocument（需要 goal 与 steps[]）: {path}")
    return data


__all__ = ["find_massomics_plan_json", "load_plan_document"]
