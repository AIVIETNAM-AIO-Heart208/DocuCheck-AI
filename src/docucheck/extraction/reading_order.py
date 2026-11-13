"""Reading order for one selected, predominantly horizontal text block.

Use pixel polygons to estimate skew before grouping rows. Region IDs and text
contents do not determine geometry, and no selected region is added or removed.
This is a block resolver, not a full-page/multi-column layout detector.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, pi, sin
from statistics import median


@dataclass(frozen=True)
class ReadingOrder:
    lines: tuple[tuple[str, ...], ...]
    angle: float
    coordinate_source: str
    ambiguous: bool = False

    @property
    def region_ids(self) -> list[str]:
        return [key for line in self.lines for key in line]

    def text(self, regions: dict) -> str | None:
        return (
            "\n".join(
                " ".join(regions[key]["text"] for key in line) for line in self.lines
            )
            or None
        )

    def audit(self, selected: list[str]) -> dict:
        return {
            "method": "deskewed_rows_v1",
            "coordinate_source": self.coordinate_source,
            "deskew_angle_degrees": round(degrees(self.angle), 4),
            "selected_region_ids": list(selected),
            "ordered_region_ids": self.region_ids,
            "line_region_ids": [list(line) for line in self.lines],
            "reordered": self.region_ids != selected,
            "ambiguous": self.ambiguous,
        }


@dataclass(frozen=True)
class _Region:
    key: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return self.y1 - self.y0


def _skew(polygons: list[list]) -> float:
    # Long horizontal edges carry more orientation evidence than tiny crops.
    # A weighted median tolerates outlier boxes; vertex start/winding is irrelevant.
    edges = []
    for points in polygons:
        for a, b in zip(points, points[1:] + points[:1]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            if dx < 0:
                dx, dy = -dx, -dy
            if dx > 0 and abs(dy) < dx:
                edges.append((atan2(dy, dx), dx))
    half_weight = sum(weight for _, weight in edges) / 2
    weight_so_far = 0
    for angle, weight in sorted(edges):
        weight_so_far += weight
        if weight_so_far >= half_weight:
            return angle
    return 0.0


def _same_row(a: _Region, b: _Region) -> bool:
    # Compare every member, not just the last appended fragment, to prevent a
    # staircase of near neighbours from merging two distinct address lines.
    return abs(a.cy - b.cy) <= 0.55 * min(a.height, b.height)


def order_regions(regions: dict, selected: list[str]) -> ReadingOrder:
    """Order validated adapter regions without mutating their IDs or OCR text.

    Polygon coordinates must share a pixel space. If polygons are unavailable,
    use bounding boxes for *all* selected regions, never a mixture of both units.
    """
    if not selected:
        return ReadingOrder((), 0.0, "polygon")
    use_polygons = all(regions[key].get("polygon") for key in selected)
    polygons = {}
    for key in selected:
        region = regions[key]
        if use_polygons:
            polygons[key] = region["polygon"]
        else:
            x0, y0, x1, y1 = region["bbox"]
            polygons[key] = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
    angle = _skew(list(polygons.values())) if use_polygons else 0.0
    assert -pi / 4 <= angle <= pi / 4
    c, s = cos(angle), sin(angle)
    projected = []
    for key, points in polygons.items():
        xs = [x * c + y * s for x, y in points]
        ys = [-x * s + y * c for x, y in points]
        projected.append(_Region(key, min(xs), min(ys), max(xs), max(ys)))

    rows: list[list[_Region]] = []
    ambiguous = False
    for region in sorted(projected, key=lambda r: (r.cy, r.x0, r.x1, r.key)):
        matches = [row for row in rows if all(_same_row(region, r) for r in row)]
        if not matches:
            rows.append([region])
            continue
        ambiguous |= len(matches) > 1
        nearest = min(
            matches, key=lambda row: abs(region.cy - median(r.cy for r in row))
        )
        nearest.append(region)

    rows.sort(key=lambda row: (median(r.cy for r in row), min(r.x0 for r in row)))
    lines = []
    for row in rows:
        row.sort(key=lambda r: (r.x0, r.cy, r.x1, r.key))
        for i, a in enumerate(row):
            for b in row[i + 1 :]:
                overlap = min(a.x1, b.x1) - max(a.x0, b.x0)
                if overlap > 0.5 * min(a.x1 - a.x0, b.x1 - b.x0):
                    ambiguous = True
        lines.append(tuple(r.key for r in row))
    return ReadingOrder(
        tuple(lines), angle, "polygon" if use_polygons else "bbox", ambiguous
    )
