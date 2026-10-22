"""把一次出图的参数记录写回 plot_config，便于对照原表版本。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def edit_record_path(png_path: str | Path) -> Path:
    png = Path(png_path)
    return png.with_suffix(".edit_record.json")


def load_edit_record(png_path: str | Path) -> dict[str, Any] | None:
    path = edit_record_path(png_path)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _source_fingerprint(source_csv: str) -> dict[str, Any]:
    name = Path(source_csv).name if source_csv else ""
    path = Path(source_csv) if source_csv else None
    if path is None or not path.is_file():
        return {"source_name": name, "source_sha256": "", "source_bytes": None}
    raw = path.read_bytes()
    return {
        "source_name": path.name,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_bytes": len(raw),
    }


def build_parameter_record(png_path: str | Path) -> dict[str, Any] | None:
    """汇总 R 写出的修改记录、原表指纹和导出文件。不读取或改写原表以外的内容。"""
    png = Path(png_path)
    record = load_edit_record(png)
    if not record:
        return None
    detail = {
        key: value
        for key, value in record.items()
        if key not in {"source_csv", "classified_csv", "filtered_csv"}
    }
    payload = {
        "edit_kind": str(record.get("edit_kind") or ""),
        "source_unchanged": bool(record.get("source_unchanged")),
        **_source_fingerprint(str(record.get("source_csv") or "")),
        "exports": {
            "png": png.is_file(),
            "svg": png.with_suffix(".svg").is_file(),
            "pdf": png.with_suffix(".pdf").is_file(),
        },
        "detail": detail,
    }
    return payload


def attach_parameter_record(png_path: str | Path, config_path: str | Path) -> dict[str, Any] | None:
    """把参数记录写进已有 plot_config。没有 R 记录时不改配置文件。"""
    record = build_parameter_record(png_path)
    if not record:
        return None
    path = Path(config_path)
    payload: dict[str, Any] = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if isinstance(loaded, dict):
            payload = loaded
    payload["parameter_record"] = record
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def score_plot_method_sentence(
    plot_type: str,
    score_style: str = "",
    *,
    has_record: bool = False,
) -> str:
    """得分图由 ggplot2 绘制。没有 C 的参数记录时不写，避免把 B 的原图说成 ggplot2。"""
    if plot_type not in {"pca", "plsda"} or not has_record:
        return ""
    name = "PLS-DA" if plot_type == "plsda" else "PCA"
    if str(score_style or "").startswith("ggplot"):
        look = "theme_classic，无网格，并按组填充 95% 椭圆"
    else:
        look = "灰网格、坐标 t[1]/t[2]，以及全体样本一个 Hotelling T² 椭圆。这是 SIMCA 版式，不是 SIMCA 软件"
    return (
        f"作图软件：{name} 由 ggplot2 绘制（{look}）。"
        "坐标来自已有得分表，没有重新拟合模型。"
    )


def parameter_record_caption(record: dict[str, Any] | None) -> str:
    line = parameter_record_line(record).strip()
    if line.startswith("- "):
        return line[2:]
    return line


def enrich_caption(
    caption: str,
    plot_type: str,
    record: dict[str, Any] | None,
    *,
    score_style: str = "",
) -> str:
    """图注补上参数记录。得分图在确有 C 的重绘记录时写明 ggplot2。"""
    text = str(caption or "").rstrip()
    parts = [text] if text else []
    detail = record.get("detail") if isinstance(record, dict) else None
    style = score_style or (str(detail.get("score_style") or "") if isinstance(detail, dict) else "")
    method = score_plot_method_sentence(plot_type, style, has_record=bool(record))
    if method and "ggplot2" not in text:
        parts.append(method)
    rec = parameter_record_caption(record)
    if rec and "参数记录" not in text:
        parts.append(rec)
    return "\n".join(part for part in parts if part)


def parameter_record_line(record: dict[str, Any] | None) -> str:
    """聊天里的一行说明：这次是样式还是重算，以及原表版本。"""
    if not isinstance(record, dict) or not record:
        return ""
    kind = {
        "style": "样式重绘",
        "analysis_param": "按原表重算筛选",
        "analysis_method": "分析方法未在作图层执行",
    }.get(str(record.get("edit_kind") or ""), "已重绘")
    name = str(record.get("source_name") or "原表")
    unchanged = "原表未改写" if record.get("source_unchanged") else "原表状态未记录"
    sha = str(record.get("source_sha256") or "")[:12]
    version = f"，数据版本 {sha}" if sha else ""
    detail = record.get("detail") if isinstance(record.get("detail"), dict) else {}
    bits: list[str] = []
    if detail.get("n_up") is not None:
        bits.append(f"上调 {detail.get('n_up')}，下调 {detail.get('n_down')}")
    if detail.get("n_pass") is not None:
        bits.append(f"通过阈值 {detail.get('n_pass')}，图上 {detail.get('n_plotted')}")
    elif detail.get("n_after_vip") is not None:
        bits.append(f"VIP 筛选后 {detail.get('n_after_vip')} 行，图上 {detail.get('n_plotted')}")
    if detail.get("n_after_fdr") is not None:
        bits.append(f"FDR 后 {detail.get('n_after_fdr')} 条")
    if detail.get("x_name") and detail.get("y_name"):
        bits.append(f"坐标 {detail.get('x_name')} × {detail.get('y_name')}")
    extra = ("；" + "；".join(bits)) if bits else ""
    exports = record.get("exports") if isinstance(record.get("exports"), dict) else {}
    files = [label for label, key in (("PDF", "pdf"), ("SVG", "svg")) if exports.get(key)]
    export_bit = f"，已导出 {'/'.join(files)}" if files else ""
    return f"- 参数记录：{kind}，{unchanged}（{name}{version}）{extra}{export_bit}\n"
