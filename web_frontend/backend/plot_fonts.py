"""matplotlib 中文字体配置（Agent 重绘 PNG 时避免中文显示为方框）。"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from matplotlib import font_manager
from matplotlib.font_manager import FontProperties

logger = logging.getLogger(__name__)

PREFERRED_CJK_FONTS = (
    "Noto Sans CJK SC",
    "Noto Sans CJK JP",
    "Noto Sans CJK TC",
    "WenQuanYi Micro Hei",
    "WenQuanYi Zen Hei",
    "Source Han Sans SC",
    "SimHei",
    "Microsoft YaHei",
    "PingFang SC",
    "Arial Unicode MS",
)

_KNOWN_CJK_FONT_FILES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)


def _is_cjk_font_file(path: str) -> bool:
    low = path.lower()
    return any(
        token in low
        for token in (
            "notosanscjk",
            "noto sans cjk",
            "sourcehansans",
            "wqy",
            "wenquanyi",
            "simhei",
            "yahei",
            "pingfang",
            "sarasa",
        )
    )


def _pick_bold_pair(regular: Path) -> Path | None:
    name = regular.name.lower()
    if "regular" in name:
        bold_name = regular.name.replace("Regular", "Bold").replace("regular", "bold")
        bold_path = regular.with_name(bold_name)
        if bold_path.is_file():
            return bold_path
    bold_candidate = regular.parent / "NotoSansCJK-Bold.ttc"
    if bold_candidate.is_file():
        return bold_candidate
    return None


@lru_cache(maxsize=1)
def _resolve_cjk_font_files() -> tuple[str, str | None]:
    """返回 (regular_path, bold_path|None)。"""
    for candidate in _KNOWN_CJK_FONT_FILES:
        path = Path(candidate)
        if path.is_file():
            bold = _pick_bold_pair(path)
            return str(path), str(bold) if bold else None

    for name in PREFERRED_CJK_FONTS:
        try:
            path = font_manager.findfont(name, fallback_to_default=False)
        except Exception:
            continue
        if not path or "dejavu" in path.lower():
            continue
        regular = Path(path)
        if regular.is_file():
            bold = _pick_bold_pair(regular)
            return str(regular), str(bold) if bold else None

    for path_str in font_manager.findSystemFonts():
        if not _is_cjk_font_file(path_str):
            continue
        regular = Path(path_str)
        if "bold" in regular.name.lower():
            continue
        bold = _pick_bold_pair(regular)
        return str(regular), str(bold) if bold else None

    logger.warning("未找到中文字体文件，图中中文可能显示为方框")
    return "", None


def cjk_fontproperties(*, size: float | int | None = None, bold: bool = False) -> FontProperties:
    """按字体文件路径构造 FontProperties，避免 fontweight 触发回退到 DejaVu。"""
    regular, bold_path = _resolve_cjk_font_files()
    path = bold_path if bold and bold_path else regular
    if not path:
        props = FontProperties()
    else:
        props = FontProperties(fname=path)
    if size is not None:
        props.set_size(size)
    return props


@lru_cache(maxsize=1)
def configure_matplotlib_cjk() -> str:
    """配置 matplotlib 全局字体，返回字体族名（供日志）。"""
    import matplotlib.pyplot as plt

    regular, _ = _resolve_cjk_font_files()
    if not regular:
        return "DejaVu Sans"

    try:
        font_manager.fontManager.addfont(regular)
    except Exception:
        pass

    family = FontProperties(fname=regular).get_name()
    current = list(plt.rcParams.get("font.sans-serif", []))
    plt.rcParams["font.sans-serif"] = [family, *[f for f in current if f != family]]
    plt.rcParams["axes.unicode_minus"] = False
    logger.info("matplotlib CJK font file: %s (family=%s)", regular, family)
    return family
