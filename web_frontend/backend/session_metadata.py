"""解析/补全会话 metadata.csv。"""
from __future__ import annotations

import shutil
from pathlib import Path

from src.platform_utils import PROJECT_ROOT, normalize_display_path


def resolve_metadata_csv(upload_dir: str | Path) -> str:
    """
    优先使用会话 inputspace 下的 metadata.csv；
    若不存在则回退到项目根 inputspace/metadata.csv 并复制到会话目录。
    """
    upload = Path(upload_dir).resolve()
    session_meta = upload / "metadata.csv"
    if session_meta.is_file():
        return normalize_display_path(session_meta)

    global_meta = PROJECT_ROOT / "inputspace" / "metadata.csv"
    if global_meta.is_file():
        upload.mkdir(parents=True, exist_ok=True)
        shutil.copy2(global_meta, session_meta)
        return normalize_display_path(session_meta)

    raise FileNotFoundError(
        f"未找到 metadata.csv。请在上传目录放置 metadata.csv（Sample,Group 列）：{upload}"
    )
