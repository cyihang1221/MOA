"""可逆操作日志（JSONL + jsonpatch）。"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import jsonpatch
except ImportError:
    jsonpatch = None  # type: ignore


def _hash_obj(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def journal_path_for_output(output_root: Path, subdir: str) -> Path:
    return Path(output_root) / subdir / "visual_edit_journal.jsonl"


def append_journal_event(
    *,
    output_root: Path,
    subdir: str,
    event_type: str,
    before: dict[str, Any],
    after: dict[str, Any],
    user_instruction: str = "",
    evidence_refs: list[dict[str, Any]] | None = None,
    validation: dict[str, Any] | None = None,
    output_files: list[str] | None = None,
) -> Path:
    path = journal_path_for_output(output_root, subdir)
    path.parent.mkdir(parents=True, exist_ok=True)
    forward = []
    reverse = []
    if jsonpatch is not None:
        try:
            forward = jsonpatch.make_patch(before, after).patch
            reverse = jsonpatch.make_patch(after, before).patch
        except Exception:
            forward = []
            reverse = []
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "instruction": (user_instruction or "")[:2000],
        "before_hash": _hash_obj(before),
        "after_hash": _hash_obj(after),
        "forward_patch": forward,
        "reverse_patch": reverse,
        "evidence_refs": evidence_refs or [],
        "validation": validation or {},
        "output_files": output_files or [],
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return path


def apply_reverse_patch(config: dict[str, Any], reverse_patch: list[dict[str, Any]]) -> dict[str, Any]:
    if jsonpatch is None or not reverse_patch:
        return dict(config)
    try:
        return jsonpatch.apply_patch(config, reverse_patch, in_place=False)
    except Exception:
        return dict(config)
