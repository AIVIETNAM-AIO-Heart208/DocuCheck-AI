"""Local-only plotting helpers for receipt annotations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from PIL import Image

from docucheck.data.loader import resolve_dataset_root


def plot_receipt_record(record: dict[str, Any], *, ax=None, show_text: bool = False):
    """Draw KIE polygons and labels over one local receipt image."""
    image_path = Path(record["image_path"])
    image = Image.open(image_path).convert("RGB")
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 10))
    ax.imshow(image)
    for index, region in enumerate(record.get("regions", [])):
        polygon = region.get("polygon")
        if not polygon:
            continue
        label = region.get("label_raw") or "unknown label"
        patch = Polygon(polygon, closed=True, fill=False, edgecolor="#e4572e", linewidth=2)
        ax.add_patch(patch)
        x, y = polygon[0]
        caption = f"{index}: {label}"
        if show_text and region.get("text_raw"):
            caption += f" | {region['text_raw'][:48]}"
        ax.text(x, y, caption, color="white", fontsize=8, backgroundcolor="#e4572e")
    ax.set_title("Local MC-OCR annotation overlay")
    ax.axis("off")
    return ax


def plot_standardized_record(
    record: dict[str, Any],
    *,
    dataset_root: str | Path | None = None,
    ax=None,
    region_key: str = "regions",
    show_text: bool = False,
):
    """Draw normalized manifest polygons without duplicating notebook logic."""
    root = resolve_dataset_root(dataset_root)
    image_path = root / record["image_path"]
    image = Image.open(image_path).convert("RGB")
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 10))
    ax.imshow(image)
    color = "#087e8b" if region_key == "regions" else "#6c5ce7"
    for index, region in enumerate(record.get(region_key, [])):
        polygon = region.get("polygon")
        if not polygon:
            continue
        label = region.get("label_raw") or "text"
        patch = Polygon(polygon, closed=True, fill=False, edgecolor=color, linewidth=2)
        ax.add_patch(patch)
        x, y = polygon[0]
        caption = f"{index}: {label}"
        if region.get("canonical_field"):
            caption += f" -> {region['canonical_field']}"
        if show_text and region.get("text_raw"):
            caption += f" | {region['text_raw'][:48]}"
        ax.text(x, y, caption, color="white", fontsize=8, backgroundcolor=color)
    ax.set_title(f"Standardized {region_key}")
    ax.axis("off")
    return ax
