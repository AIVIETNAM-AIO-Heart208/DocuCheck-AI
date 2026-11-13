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
    _, identity, _, reason = options[0]
    selected = [options[0]]
    if reason == "projected_row":
        # Expand only along the anchor's row and through adjacent text boxes.
        # Every fragment is checked against the anchor to prevent row drift.
        anchor = regions[identity]["polygon"]
        ax = sum(p[0] for p in anchor) / len(anchor)
        ay = sum(p[1] for p in anchor) / len(anchor)
        ah = max(
            1, (abs(anchor[3][1] - anchor[0][1]) + abs(anchor[2][1] - anchor[1][1])) / 2
        )
        remaining = options[1:]
        while remaining:
            left = min(p[0] for _, i, _, _ in selected for p in regions[i]["polygon"])
            right = max(p[0] for _, i, _, _ in selected for p in regions[i]["polygon"])
            added = False
            for option in list(remaining):
                _, i, _, why = option
                p = regions[i]["polygon"]
                cx = sum(v[0] for v in p) / len(p)
                cy = sum(v[1] for v in p) / len(p)
                lo, hi = min(v[0] for v in p), max(v[0] for v in p)
                gap = max(left - hi, lo - right, 0)
                if (
                    why == "projected_row"
                    and gap <= 1.5 * ah
                    and (hi <= left + 0.25 * ah or lo >= right - 0.25 * ah)
                    and abs(cy - ay - page_slope * (cx - ax)) <= 0.4 * ah
                ):
                    selected.append(option)
                    remaining.remove(option)
                    added = True
            if not added:
                break
        selected.sort(
            key=lambda option: min(p[0] for p in regions[option[1]]["polygon"])
        )
    return [
        {
            "region_id": identity,
            "text": text,
            "relation_reason": reason,
            "row_residual": score,
            "start": regions[identity]["text"].find(text),
            "end": regions[identity]["text"].find(text) + len(text),
        }
        for score, identity, text, reason in selected
    ]
