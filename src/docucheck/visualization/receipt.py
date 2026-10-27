"""Local-only plotting helpers for receipt annotations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from PIL import Image


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
