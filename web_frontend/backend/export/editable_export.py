"""Create editable metadata sidecars for rendered PNG figures.

The web editor uses the original PNG as a background and stores only overlay
objects in a JSON sidecar. This preserves the exact Matplotlib/R/ggplot style
while still allowing titles and annotations to be edited in the browser.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EDITABLE_VERSION = 1


def editable_json_path(image_path: str | Path) -> Path:
    image = Path(image_path)
    return image.with_name(f"{image.stem}.editable.json")


def build_editable_metadata(
    image_path: str | Path,
    *,
    title: str | None = None,
    title_position: str = "top-center",
    width: int | None = None,
    height: int | None = None,
    objects: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    image = Path(image_path)
    return {
        "version": EDITABLE_VERSION,
        "image": image.name,
        "title": title or image.stem.replace("_", " "),
        "title_position": title_position,
        "width": width,
        "height": height,
        "objects": objects or [],
    }


def save_editable_metadata(
    image_path: str | Path,
    *,
    title: str | None = None,
    title_position: str = "top-center",
    width: int | None = None,
    height: int | None = None,
    objects: list[dict[str, Any]] | None = None,
) -> Path:
    out = editable_json_path(image_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            build_editable_metadata(
                image_path,
                title=title,
                title_position=title_position,
                width=width,
                height=height,
                objects=objects,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return out


def save_editable_figure(
    fig: Any,
    image_path: str | Path,
    *,
    title: str | None = None,
    title_position: str = "top-center",
    plotly_fig: Any | None = None,
    skip_plotly: bool = False,
    **savefig_kwargs: Any,
) -> Path:
    """Save a Matplotlib figure, editable sidecar, and optional Plotly JSON."""
    fig.savefig(image_path, **savefig_kwargs)
    save_editable_metadata(image_path, title=title, title_position=title_position)
    if not skip_plotly:
        if plotly_fig is not None:
            from web_frontend.backend.export.plotly_export import maybe_save_plotly

            maybe_save_plotly(plotly_fig, image_path)
        else:
            from web_frontend.backend.export.plotly_export import maybe_save_plotly_from_matplotlib

            maybe_save_plotly_from_matplotlib(fig, image_path)
    return Path(image_path)


def ensure_editable_sidecars(
    directory: str | Path,
    *,
    title_map: dict[str, str] | None = None,
) -> list[Path]:
    """Create missing sidecars for every PNG in a directory."""
    root = Path(directory)
    if not root.is_dir():
        return []
    created: list[Path] = []
    title_map = title_map or {}
    for image in sorted(root.glob("*.png")):
        sidecar = editable_json_path(image)
        if sidecar.exists():
            continue
        save_editable_metadata(image, title=title_map.get(image.name))
        created.append(sidecar)
    return created
