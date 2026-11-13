"""Label relations projected along OCR polygon baselines, independent of order."""

import re
from statistics import median


def labels(regions, key, match):
    target = regions[key]
    polygon = target["polygon"]
    tx = sum(p[0] for p in polygon) / len(polygon)
    ty = sum(p[1] for p in polygon) / len(polygon)
    slopes = [
        (r["polygon"][1][1] - r["polygon"][0][1])
        / (r["polygon"][1][0] - r["polygon"][0][0])
        for r in regions.values()
        if len(r["text"]) >= 5 and abs(r["polygon"][1][0] - r["polygon"][0][0]) > 1
    ]
    page_slope = median(slopes) if slopes else 0
    options = []
    for identity, region in regions.items():
        text = region["text"]
        if not re.search(r"[^\W\d_]", text, re.UNICODE):
            continue
        if identity == key:
            prefix = text[: match.start()]
            # Scope inline evidence to the label immediately preceding this number.
            prefix = re.split(r"\d+(?:[.,]\d+)*", prefix)[-1].strip()
            if prefix:
                options.append((0, identity, prefix, "inline_prefix"))
            continue
        p = region["polygon"]
        cx = sum(v[0] for v in p) / len(p)
        cy = sum(v[1] for v in p) / len(p)
        slope = page_slope
        height = max(1, (abs(p[3][1] - p[0][1]) + abs(p[2][1] - p[1][1])) / 2)
        residual = abs(ty - (cy + slope * (tx - cx))) / height
        if residual < 0.65:
            options.append((residual, identity, text, "projected_row"))
    options.sort(key=lambda v: (v[0], v[1]))
    if not options:
        return []
    score, identity, text, reason = options[0]
    return [
        {
            "region_id": identity,
            "text": text,
            "relation_reason": reason,
            "row_residual": score,
            "start": regions[identity]["text"].find(text),
            "end": regions[identity]["text"].find(text) + len(text),
        }
    ]
