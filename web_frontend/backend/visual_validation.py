"""VisualIR / plot_config patch 的确定性校验（软约束）。"""
from __future__ import annotations

import copy
import re
from typing import Any

_HEX = re.compile(r"^#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?$")

_THRESHOLD_KEYS = frozenset({"thresholds", "x_min", "x_max", "y_min", "y_max", "padj", "pvalue", "fdr"})


def _is_threshold_patch(patch: dict[str, Any]) -> bool:
    blob = str(patch).lower()
    if any(k in blob for k in _THRESHOLD_KEYS):
        return True
    axes = patch.get("axes")
    if isinstance(axes, dict):
        for k in ("x_min", "x_max", "y_min", "y_max"):
            if axes.get(k) is not None:
                return True
    return False


def validate_plot_patch(
    *,
    patch: dict[str, Any],
    current_config: dict[str, Any],
    color_keys: list[str],
    metadata_columns: list[str] | None,
    evidence_cards: list[dict[str, Any]] | None,
    user_instruction: str,
    plot_type: str = "",
) -> dict[str, Any]:
    """返回 accepted_patch, warnings, errors。"""
    from web_frontend.backend.plot_theme import sanitize_volcano_plot_patch

    if plot_type == "volcano":
        patch = sanitize_volcano_plot_patch(patch)
    accepted = copy.deepcopy(patch)
    warnings: list[str] = []
    errors: list[str] = []
    meta_cols = {str(c) for c in (metadata_columns or [])}

    color_by = accepted.get("color_by")
    if color_by is not None:
        cb = str(color_by).strip()
        if cb and meta_cols and cb not in meta_cols:
            errors.append(f"color_by `{cb}` 不在 metadata 列中")
            accepted.pop("color_by", None)

    palette = accepted.get("palette")
    if isinstance(palette, dict) and color_keys:
        unknown = [k for k in palette if str(k) not in {str(x) for x in color_keys}]
        if unknown:
            warnings.append(f"palette 键 {unknown[:5]} 不在当前数据类别中，已移除")
            for k in unknown:
                palette.pop(k, None)

    for section in ("palette", "colors"):
        sec = accepted.get(section)
        if isinstance(sec, dict):
            for k, v in list(sec.items()):
                if isinstance(v, str) and not _HEX.fullmatch(v.strip()):
                    warnings.append(f"无效颜色 {section}.{k}，已忽略")
                    sec.pop(k, None)

    if _is_threshold_patch(accepted):
        user_wants_threshold = bool(
            re.search(r"阈值|threshold|p\s*值|fdr|padj|log2", user_instruction or "", re.I)
        )
        if not user_wants_threshold:
            warnings.append("patch 含阈值/坐标范围字段；软约束下未自动应用，已剥离 axes 数值改动")
            axes = accepted.get("axes")
            if isinstance(axes, dict):
                for k in ("x_min", "x_max", "y_min", "y_max"):
                    axes.pop(k, None)

    if evidence_cards:
        lit_fields = {h for c in evidence_cards for h in (c.get("field_hints") or [])}
        if "color_by" in accepted and "color_by" not in lit_fields and not re.search(
            r"按|分组|group|batch|着色", user_instruction or "", re.I
        ):
            warnings.append("color_by 变更无文献字段支持，但用户指令可能覆盖（已保留需用户确认）")

    if errors:
        accepted = {}

    return {
        "accepted_patch": accepted,
        "warnings": warnings,
        "errors": errors,
    }


def validate_merge_options(
    *,
    options: dict[str, Any],
    sources: list[str],
) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    opts = dict(options)
    if len(sources) < 2:
        errors.append("拼图至少需要 2 张源图")
    cols = opts.get("cols")
    if cols is not None:
        try:
            c = int(cols)
            if c < 1:
                errors.append("cols 必须 >= 1")
        except (TypeError, ValueError):
            errors.append("cols 无效")
    label_mode = str(opts.get("label_mode") or "upper")
    if label_mode not in {"upper", "lower", "num", "none", "custom"}:
        warnings.append(f"未知 label_mode `{label_mode}`，回退 upper")
        opts["label_mode"] = "upper"
    return {"accepted_options": opts, "warnings": warnings, "errors": errors}
