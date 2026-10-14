"""把 final_report.md 转成 PDF（需求 FR-5.5）。排版对齐网页报告：图卡片 + E/C/B 模块。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")
_LIST_RE = re.compile(r"^[-*]\s+")
_OL_RE = re.compile(r"^\d+[.)]\s+")

# 网页 :root 色
_NAVY = (15, 23, 42)
_ACCENT = (37, 99, 235)
_TEXT = (15, 23, 42)
_MUTED = (100, 116, 139)
_BORDER = (226, 232, 240)
_WHITE = (255, 255, 255)
_PAGE_BG = (244, 246, 251)
_CARD_BG = (255, 255, 255)
_SOFT = (248, 250, 252)

_ECB_STYLE = {
    "e": {"bar": (46, 125, 50), "fill": (236, 253, 245)},
    "c": {"bar": (106, 90, 205), "fill": (245, 243, 255)},
    "b": {"bar": (199, 119, 0), "fill": (255, 247, 237)},
}

_FONT_REGULAR = (
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
)
_FONT_BOLD = (
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"),
)

FONT_NAME = "ReportFont"


def _first_existing(paths: tuple[Path, ...]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None


def _cjk_fonts() -> tuple[Path, Path | None]:
    regular = _first_existing(_FONT_REGULAR)
    if regular is None:
        raise RuntimeError(
            "未找到 CJK 字体（NotoSansCJK / wqy-microhei / DroidSansFallback），无法导出含中文的 PDF"
        )
    bold = _first_existing(_FONT_BOLD)
    return regular, bold


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


def _strip_inline_md(text: str) -> str:
    out = _BOLD_RE.sub(r"\1", text or "")
    return re.sub(r"[`_]+", "", out).strip()


def _split_caption(caption: str) -> tuple[str, list[tuple[str, str]], list[str]]:
    """把图注拆成：标题、字段模块、补充说明。"""
    title_parts: list[str] = []
    fields: list[tuple[str, str]] = []
    notes: list[str] = []
    field_re = re.compile(
        r"^(?:\*\*(.+?)\*\*|([\w\u4e00-\u9fff（）()]{2,16}))[：:]\s*(.*)$"
    )
    for raw in (caption or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        hit = field_re.match(line)
        if hit:
            key = (hit.group(1) or hit.group(2) or "").strip()
            val = (hit.group(3) or "").strip()
            if key and not key.lower().startswith("http"):
                fields.append((key, val))
                continue
        text = _strip_inline_md(line)
        if fields:
            notes.append(text)
        else:
            title_parts.append(text)
    return "\n".join(title_parts).strip(), fields, notes


def _first_heading(markdown: str) -> str:
    for raw in (markdown or "").splitlines():
        hit = _HEADING_RE.match(raw.strip())
        if hit:
            return _strip_inline_md(hit.group(2))
    return "分析报告"


def _load_sidecars(md_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    insights: dict[str, Any] = {}
    cards_path = md_dir / "figure_cards.json"
    if cards_path.is_file():
        try:
            raw = json.loads(cards_path.read_text(encoding="utf-8"))
            cards = list(raw.get("figure_cards") or [])
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            cards = []
    insights_path = md_dir / "report_insights.json"
    if insights_path.is_file():
        try:
            insights = json.loads(insights_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            insights = {}
    return cards, insights


def _ecb_lines(key: str, block: dict[str, Any]) -> list[str]:
    if not block:
        return []
    if block.get("status") == "placeholder" and block.get("placeholder_reason"):
        return [str(block["placeholder_reason"]).strip()]
    if key == "e":
        return [str(x).strip() for x in (block.get("bullets") or []) if str(x).strip()]
    if key == "c":
        lines = [str(x).strip() for x in (block.get("patterns") or []) if str(x).strip()]
        sep = str(block.get("group_separation") or "").strip()
        if sep and sep.upper() != "N/A":
            lines.append(sep)
        notable = str(block.get("notable_features") or "").strip()
        if notable:
            lines.append(notable)
        if not lines and block.get("placeholder_reason"):
            lines = [str(block["placeholder_reason"]).strip()]
        return lines
    if key == "b":
        parts = [
            str(block.get("what_it_shows") or "").strip(),
            str(block.get("link_to_objective") or "").strip(),
            str(block.get("caveats") or "").strip(),
        ]
        return [p for p in parts if p]
    md = str(block.get("markdown") or "").strip()
    if md:
        cleaned = re.sub(r"^#+\s*", "", md, flags=re.MULTILINE).strip()
        return [cleaned[:800]] if cleaned else []
    return []


class ReportPDF:
    """fpdf2 封装：网页报告同款页眉、图卡片、E/C/B 色块。"""

    def __init__(self, *, title: str, summary: str = ""):
        from fpdf import FPDF

        regular, bold = _cjk_fonts()
        self.pdf = FPDF(format="A4", unit="mm")
        self.pdf.set_auto_page_break(auto=True, margin=16)
        self.pdf.set_margins(16, 16, 16)
        self.pdf.add_font(FONT_NAME, fname=str(regular))
        if bold:
            self.pdf.add_font(FONT_NAME, style="B", fname=str(bold))
        else:
            self.pdf.add_font(FONT_NAME, style="B", fname=str(regular))
        self.title = title or "分析报告"
        self.summary = (summary or "").strip()
        self.pdf.header = self._header  # type: ignore[method-assign]
        self.pdf.footer = self._footer  # type: ignore[method-assign]
        self.pdf.add_page()
        self.pdf.set_font(FONT_NAME, size=10.5)
        self.pdf.set_text_color(*_TEXT)

    @property
    def usable(self) -> float:
        return self.pdf.w - self.pdf.l_margin - self.pdf.r_margin

    def _header(self) -> None:
        pdf = self.pdf
        first = pdf.page_no() == 1
        bar_h = 24 if first else 11
        pdf.set_fill_color(*_NAVY)
        pdf.rect(0, 0, pdf.w, bar_h, "F")
        pdf.set_fill_color(*_ACCENT)
        pdf.rect(0, bar_h - 1.1, pdf.w, 1.1, "F")
        pdf.set_fill_color(*_PAGE_BG)
        pdf.rect(0, bar_h, pdf.w, pdf.h - bar_h, "F")
        pdf.set_text_color(248, 250, 252)
        if first:
            pdf.set_font(FONT_NAME, "B", 13)
            pdf.set_xy(16, 5)
            pdf.cell(self.usable, 7, "MassAgent 分析报告")
            subtitle = self.title if self.title and self.title not in {"分析报告", "Analysis report"} else ""
            if subtitle:
                pdf.set_font(FONT_NAME, "", 9.5)
                pdf.set_text_color(148, 163, 184)
                pdf.set_xy(16, 13)
                pdf.cell(self.usable, 6, subtitle)
        else:
            pdf.set_font(FONT_NAME, "B", 9)
            pdf.set_xy(16, 2.5)
            pdf.cell(self.usable, 6, f"MassAgent  ·  {self.title}")
        pdf.set_text_color(*_TEXT)
        pdf.set_y(bar_h + 8)

    def _footer(self) -> None:
        pdf = self.pdf
        pdf.set_y(-13)
        pdf.set_draw_color(*_BORDER)
        pdf.set_line_width(0.2)
        pdf.line(16, pdf.h - 14, pdf.w - 16, pdf.h - 14)
        pdf.set_font(FONT_NAME, "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(0, 8, f"MassAgent  ·  {pdf.page_no()}", align="C")
        pdf.set_text_color(*_TEXT)

    def _ensure(self, height: float) -> None:
        if self.pdf.will_page_break(height):
            self.pdf.add_page()

    def _font(self, *, bold: bool = False, size: float = 10.5) -> None:
        self.pdf.set_font(FONT_NAME, "B" if bold else "", size)

    def _text_height(self, text: str, width: float, line_h: float, *, bold: bool = False, size: float = 10.5) -> float:
        body = text or " "
        self._font(bold=bold, size=size)
        lines = self.pdf.multi_cell(width, line_h, body, dry_run=True, output="LINES")
        return max(line_h, line_h * len(lines))

    def write_text(
        self,
        text: str,
        *,
        size: float = 10.5,
        bold: bool = False,
        line_h: float = 5.6,
        indent: float = 0,
        color: tuple[int, int, int] = _TEXT,
        after: float = 1.2,
    ) -> None:
        body = text or " "
        width = max(20.0, self.usable - indent)
        h = self._text_height(body, width, line_h, bold=bold, size=size)
        self._ensure(h + 1)
        self.pdf.set_text_color(*color)
        self._font(bold=bold, size=size)
        self.pdf.set_x(self.pdf.l_margin + indent)
        self.pdf.multi_cell(width, line_h, body, new_x="LMARGIN", new_y="NEXT")
        self.pdf.set_text_color(*_TEXT)
        if after:
            self.pdf.ln(after)

    def section_title(self, text: str) -> None:
        self._ensure(14)
        self.pdf.ln(2)
        self.write_text(text, size=13, bold=True, line_h=7, after=0.6)
        y = self.pdf.get_y()
        self.pdf.set_draw_color(*_ACCENT)
        self.pdf.set_line_width(0.7)
        self.pdf.line(self.pdf.l_margin, y, self.pdf.l_margin + 22, y)
        self.pdf.ln(3)

    def heading(self, level: int, text: str) -> None:
        if level <= 1:
            self._ensure(16)
            self.write_text(text, size=16, bold=True, line_h=8, after=2)
            return
        if level == 2:
            self.section_title(text)
            return
        if level == 3:
            self.write_text(text, size=11.5, bold=True, line_h=6.4, after=1.2)
            return
        self.write_text(text, size=10.5, bold=True, line_h=5.8, color=_MUTED, after=1)

    def embed_image(self, img_path: Path, *, max_w: float | None = None) -> None:
        usable = max_w or self.usable
        max_h = self.pdf.h - self.pdf.t_margin - self.pdf.b_margin - 28
        try:
            from PIL import Image

            with Image.open(img_path) as im:
                w_px, h_px = im.size
            if w_px <= 0 or h_px <= 0:
                raise ValueError("invalid image size")
            aspect = h_px / w_px
            w_mm = min(usable, 178)
            h_mm = w_mm * aspect
            if h_mm > max_h:
                h_mm = max_h
                w_mm = h_mm / aspect
        except Exception:
            w_mm, h_mm = min(usable, 160), 90

        self._ensure(h_mm + 8)
        x = self.pdf.l_margin + max(0, (self.usable - w_mm) / 2)
        y = self.pdf.get_y()
        self.pdf.set_draw_color(*_BORDER)
        self.pdf.set_line_width(0.25)
        self.pdf.set_fill_color(*_WHITE)
        self.pdf.rect(x - 1.2, y - 1.2, w_mm + 2.4, h_mm + 2.4, style="DF")
        try:
            self.pdf.image(str(img_path), x=x, y=y, w=w_mm, h=h_mm)
        except Exception as exc:
            self.write_text(f"[图无法嵌入: {img_path.name} ({exc})]", size=9, color=_MUTED)
            return
        self.pdf.set_y(y + h_mm + 4)

    def summary_banner(self) -> None:
        if not self.summary:
            return
        width = self.usable
        line_h = 5.2
        inner_w = width - 10
        h = 8 + self._text_height(self.summary, inner_w, line_h, size=9.5)
        self._ensure(h + 4)
        x, y = self.pdf.l_margin, self.pdf.get_y()
        self.pdf.set_fill_color(219, 234, 254)
        self.pdf.set_draw_color(*_ACCENT)
        self.pdf.set_line_width(0.3)
        self.pdf.rect(x, y, width, h, style="DF")
        self.pdf.set_fill_color(*_ACCENT)
        self.pdf.rect(x, y, 1.8, h, style="F")
        self.pdf.set_xy(x + 6, y + 2.5)
        self._font(bold=False, size=9.5)
        self.pdf.set_text_color(*_TEXT)
        self.pdf.multi_cell(inner_w, line_h, self.summary, new_x="LMARGIN", new_y="NEXT")
        self.pdf.set_y(y + h + 4)

    def _module_block(
        self,
        title: str,
        lines: list[str],
        *,
        bar: tuple[int, int, int],
        fill: tuple[int, int, int],
        bullets: bool = True,
    ) -> None:
        if not lines:
            return
        width = self.usable
        inner_w = width - 12
        line_h = 5.1
        body_h = 0.0
        for line in lines:
            prefix = "• " if bullets else ""
            body_h += self._text_height(prefix + line, inner_w, line_h, size=9)
        h = 8 + body_h + 3
        self._ensure(h + 2)
        x, y = self.pdf.l_margin, self.pdf.get_y()
        self.pdf.set_fill_color(*fill)
        self.pdf.set_draw_color(*_BORDER)
        self.pdf.set_line_width(0.2)
        self.pdf.rect(x, y, width, h, style="DF")
        self.pdf.set_fill_color(*bar)
        self.pdf.rect(x, y, 1.8, h, style="F")
        self.pdf.set_xy(x + 6, y + 1.8)
        self._font(bold=True, size=8)
        self.pdf.set_text_color(*_MUTED)
        self.pdf.cell(inner_w, 5, title)
        self.pdf.set_text_color(*_TEXT)
        self.pdf.set_xy(x + 6, y + 7)
        self._font(size=9)
        for line in lines:
            prefix = "• " if bullets else ""
            self.pdf.set_x(x + 6)
            self.pdf.multi_cell(inner_w, line_h, prefix + line, new_x="LMARGIN", new_y="NEXT")
        self.pdf.set_y(y + h + 2.4)

    def figure_card(self, card: dict[str, Any], *, md_dir: Path, results_dir: Path) -> None:
        fid = str(card.get("figure_id") or "Figure").strip() or "Figure"
        plot_type = str(card.get("plot_type") or "").strip()
        caption = _strip_inline_md(str(card.get("caption") or ""))
        rel = str(card.get("rel") or "").strip()
        self._ensure(48)
        self.pdf.ln(1)
        self.write_text(fid, size=12, bold=True, line_h=6.2, after=0.2)
        if plot_type:
            self.write_text(plot_type, size=8.5, color=_MUTED, line_h=4.6, after=2)

        img_path = resolve_report_image_path(rel, md_dir=md_dir, results_dir=results_dir) if rel else None
        if img_path:
            self.embed_image(img_path, max_w=self.usable - 2)
        lead, fields, notes = _split_caption(caption)
        if lead:
            self.write_text(lead, size=9.5, line_h=5.2, after=1.2)
        if fields:
            field_lines = [f"{key}：{val}" for key, val in fields if val]
            if field_lines:
                self._module_block("图注", field_lines, bar=_MUTED, fill=_WHITE, bullets=False)
        if notes:
            self.write_text(" ".join(notes), size=8.5, color=_MUTED, line_h=5.0, after=2)
        elif caption and not lead and not fields:
            self.write_text(caption, size=9.5, line_h=5.2, after=2)

        blocks = card.get("blocks") or {}
        for key in ("e", "c", "b"):
            block = blocks.get(key) or {}
            lines = _ecb_lines(key, block)
            if not lines:
                continue
            style = _ECB_STYLE[key]
            title = str(block.get("title") or key)
            use_bullets = key != "b"
            self._module_block(title, lines, bar=style["bar"], fill=style["fill"], bullets=use_bullets)
        self.pdf.ln(2)

    def markdown(self, markdown: str, *, md_dir: Path, results_dir: Path) -> None:
        table_buf: list[str] = []

        def flush_table() -> None:
            rows = list(table_buf)
            table_buf.clear()
            parsed: list[list[str]] = []
            for row in rows:
                if _TABLE_SEP_RE.match(row):
                    continue
                cells = [_strip_inline_md(c) for c in row.strip().strip("|").split("|")]
                if any(cells):
                    parsed.append(cells)
            if not parsed:
                return
            ncols = max(len(r) for r in parsed)
            for row in parsed:
                while len(row) < ncols:
                    row.append("")
            self._ensure(8 + 5.2 * len(parsed))
            try:
                self._font(size=8.5)
                self.pdf.set_draw_color(*_BORDER)
                with self.pdf.table(
                    width=self.usable,
                    line_height=5.2,
                    markdown=False,
                    text_align="LEFT",
                ) as table:
                    for i, cells in enumerate(parsed):
                        trow = table.row()
                        for cell in cells:
                            trow.cell(cell or " ")
                self.pdf.ln(2)
            except Exception:
                for row in parsed:
                    self.write_text("  |  ".join(row), size=8.5, line_h=4.8)

        for raw in (markdown or "").splitlines():
            line = raw.rstrip()
            if line.strip().startswith("|"):
                table_buf.append(line)
                continue
            if table_buf:
                flush_table()

            if not line.strip():
                self.pdf.ln(1.6)
                continue

            img = _IMG_RE.search(line)
            if img:
                rel = img.group(2).strip()
                img_path = resolve_report_image_path(rel, md_dir=md_dir, results_dir=results_dir)
                if img_path:
                    self.embed_image(img_path)
                else:
                    self.write_text(f"[缺图: {rel}]", size=9, color=_MUTED)
                continue

            heading = _HEADING_RE.match(line.strip())
            if heading:
                self.heading(len(heading.group(1)), _strip_inline_md(heading.group(2)))
                continue

            stripped = line.strip()
            if stripped in {"---", "***", "___"}:
                self._ensure(6)
                y = self.pdf.get_y() + 2
                self.pdf.set_draw_color(*_BORDER)
                self.pdf.line(self.pdf.l_margin, y, self.pdf.l_margin + self.usable, y)
                self.pdf.ln(5)
                continue
            if stripped.startswith(">"):
                quote = _strip_inline_md(stripped.lstrip(">").strip())
                self._module_block(" ", [quote], bar=_ACCENT, fill=_SOFT, bullets=False)
                continue
            if _LIST_RE.match(stripped):
                body = _LIST_RE.sub("", stripped)
                self.write_text("•  " + _strip_inline_md(body), size=10.5, line_h=5.5, indent=3)
                continue
            if _OL_RE.match(stripped):
                self.write_text(_strip_inline_md(stripped), size=10.5, line_h=5.5, indent=3)
                continue
            self.write_text(_strip_inline_md(stripped), size=10.5, line_h=5.7)

        if table_buf:
            flush_table()

    def output(self, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.pdf.output(str(dest))
        return dest


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
    dest = Path(pdf_path)
    md_dir = Path(resource_dir).resolve()
    root = Path(results_dir).resolve() if results_dir else _infer_results_dir(md_dir / "final_report.md")
    cards, insights = _load_sidecars(md_dir)
    title = _first_heading(markdown)
    summary = str(insights.get("summary") or "").strip()
    if cards:
        n_fig = len(cards)
        extra = f"共 {n_fig} 张相关图"
        summary = f"{summary}  ·  {extra}" if summary else extra

    report = ReportPDF(title=title, summary=summary)
    if summary:
        report.summary_banner()

    if cards:
        from web_frontend.backend.agent_c.report_view import split_markdown_figure_section

        prose, _figures_md = split_markdown_figure_section(markdown)
        report.section_title("图表解读")
        for card in cards:
            report.figure_card(card, md_dir=md_dir, results_dir=root)
        report.section_title("报告正文")
        # 正文里已有同名一级标题时去掉，避免与页眉重复
        prose_lines = prose.splitlines()
        if prose_lines and _HEADING_RE.match(prose_lines[0].strip()):
            first = _HEADING_RE.match(prose_lines[0].strip())
            if first and len(first.group(1)) == 1:
                prose = "\n".join(prose_lines[1:]).lstrip()
        report.markdown(prose, md_dir=md_dir, results_dir=root)
    else:
        report.markdown(markdown, md_dir=md_dir, results_dir=root)
    return report.output(dest)


__all__ = [
    "markdown_file_to_pdf",
    "markdown_to_pdf",
    "resolve_report_image_path",
]
