"""把 final_report.md 转成 PDF（需求 FR-5.5）。不改 A/B 计算。"""
from __future__ import annotations

import re
from pathlib import Path

_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")

# 优先 Noto CJK（含拉丁字形）；DroidSansFallback 仅作最后兜底
_FONT_CANDIDATES = (
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
)


def _cjk_font() -> Path | None:
    for path in _FONT_CANDIDATES:
        if path.is_file():
            return path
    return None


def _infer_results_dir(md_path: Path) -> Path:
    if md_path.parent.name == "agent_c_output":
        return md_path.parent.parent
    return md_path.parent


def resolve_report_image_path(
    rel: str,
    *,
    md_dir: Path,
    results_dir: Path | None,
) -> Path | None:
    """解析 Markdown 图片路径（相对 outputspace 或 agent_c_output）。"""
    raw = (rel or "").strip()
    if not raw or raw.startswith(("http://", "https://", "/api/", "data:")):
        return None
    if "?" in raw:
        raw = raw.split("?", 1)[0].strip()
    path = Path(raw)
    if path.is_absolute() and path.is_file():
        return path.resolve()

    bases: list[Path] = []
    if results_dir:
        root = results_dir.resolve()
        bases.extend([root, root / "agent_c_output"])
    bases.append(md_dir.resolve())

    rel_posix = raw.replace("\\", "/").lstrip("/")
    candidates: list[Path] = []
    for base in bases:
        candidates.append(base / rel_posix)
        if not rel_posix.startswith("agent_c_output/"):
            candidates.append(base / "agent_c_output" / rel_posix)
        if rel_posix.startswith("agent_c_output/"):
            candidates.append(base / rel_posix[len("agent_c_output/") :])
    if rel_posix.startswith("figures/"):
        candidates.append(md_dir / rel_posix)

    seen: set[str] = set()
    for cand in candidates:
        key = str(cand)
        if key in seen:
            continue
        seen.add(key)
        try:
            resolved = cand.resolve()
        except OSError:
            continue
        if resolved.is_file():
            return resolved
    return None


def markdown_file_to_pdf(
    md_path: str | Path,
    pdf_path: str | Path | None = None,
    *,
    results_dir: str | Path | None = None,
) -> Path:
    src = Path(md_path)
    dest = Path(pdf_path) if pdf_path else src.with_suffix(".pdf")
    text = src.read_text(encoding="utf-8")
    root = Path(results_dir).resolve() if results_dir else _infer_results_dir(src)
    return markdown_to_pdf(text, dest, resource_dir=src.parent, results_dir=root)


def markdown_to_pdf(
    markdown: str,
    pdf_path: str | Path,
    *,
    resource_dir: str | Path,
    results_dir: str | Path | None = None,
) -> Path:
    try:
        from fpdf import FPDF
    except ImportError as exc:
        raise RuntimeError("需要 fpdf2（import fpdf）才能导出 PDF") from exc

    dest = Path(pdf_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    md_dir = Path(resource_dir).resolve()
    root = Path(results_dir).resolve() if results_dir else _infer_results_dir(md_dir / "final_report.md")

    font_path = _cjk_font()
    if font_path is None:
        raise RuntimeError(
            "未找到 CJK 字体（NotoSansCJK / wqy-microhei / DroidSansFallback），无法导出含中文的 PDF"
        )

    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()
    font_name = "ReportFont"
    pdf.add_font(font_name, fname=str(font_path))
    pdf.add_font(font_name, style="B", fname=str(font_path))
    pdf.set_font(font_name, size=11)

    usable = pdf.w - pdf.l_margin - pdf.r_margin
    max_img_w = min(usable, 170)
    max_img_h = pdf.h - pdf.t_margin - pdf.b_margin - 24

    def _write(text: str, *, size: int = 11, style: str = "", skip: float = 6, indent: float = 0):
        pdf.set_font(font_name, style=style, size=size)
        x = pdf.l_margin + indent
        pdf.set_x(x)
        pdf.multi_cell(usable - indent, skip, text or " ", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(0.5)

    def _strip_inline_md(text: str) -> str:
        out = _BOLD_RE.sub(r"\1", text)
        return re.sub(r"[`_]+", "", out).strip()

    def _embed_image(img_path: Path) -> None:
        try:
            from PIL import Image

            with Image.open(img_path) as im:
                w_px, h_px = im.size
            if w_px <= 0 or h_px <= 0:
                raise ValueError("invalid image size")
            aspect = h_px / w_px
            w_mm = max_img_w
            h_mm = w_mm * aspect
            if h_mm > max_img_h:
                h_mm = max_img_h
                w_mm = h_mm / aspect
            pdf.image(str(img_path), w=w_mm, h=h_mm)
            pdf.ln(3)
        except Exception:
            try:
                pdf.image(str(img_path), w=max_img_w)
                pdf.ln(3)
            except Exception as exc:
                _write(f"[图无法嵌入: {img_path.name} ({exc})]", size=9)

    for raw in markdown.splitlines():
        line = raw.rstrip()
        if not line.strip():
            pdf.ln(2)
            continue

        img = _IMG_RE.search(line)
        if img:
            rel = img.group(2).strip()
            img_path = resolve_report_image_path(rel, md_dir=md_dir, results_dir=root)
            if img_path:
                _embed_image(img_path)
            else:
                _write(f"[缺图: {rel}]", size=9)
            continue

        heading = _HEADING_RE.match(line.strip())
        if heading:
            level = len(heading.group(1))
            title = _strip_inline_md(heading.group(2))
            sizes = {1: 16, 2: 13, 3: 12, 4: 11}
            _write(title, size=sizes.get(level, 11), style="B", skip=7 if level <= 2 else 6)
            continue

        stripped = line.strip()
        if stripped.startswith("|"):
            _write(stripped.replace("|", " │ "), size=9, skip=5)
            continue
        if stripped.startswith(">"):
            _write(_strip_inline_md(stripped.lstrip(">").strip()), size=10, skip=5, indent=4)
            continue
        if re.match(r"^[-*]\s+", stripped):
            body = re.sub(r"^[-*]\s+", "", stripped)
            _write("• " + _strip_inline_md(body), size=11, skip=5, indent=2)
            continue
        if stripped in {"---", "***", "___"}:
            pdf.ln(2)
            continue

        _write(_strip_inline_md(stripped), size=11, skip=6)

    pdf.output(str(dest))
    return dest


__all__ = [
    "markdown_file_to_pdf",
    "markdown_to_pdf",
    "resolve_report_image_path",
]
