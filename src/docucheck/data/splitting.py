"""Deterministic exact-duplicate-aware development splitting."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Any


def assign_internal_splits(
    records: list[dict[str, Any]], *, seed: int = 42, validation_fraction: float = 0.2
) -> list[dict[str, Any]]:
    """Assign internal train/dev by image-content group, never splitting duplicates."""
    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be strictly between 0 and 1")
    grouped = defaultdict(list)
    for index, record in enumerate(records):
        group_id = record.get("image_group_id") or f"invalid:{record.get('image_id', index)}"
        grouped[group_id].append(index)
    group_ids = sorted(grouped)
    if not group_ids:
        return []
    random.Random(seed).shuffle(group_ids)
    dev_group_count = (
        min(len(group_ids) - 1, max(1, round(len(group_ids) * validation_fraction)))
        if len(group_ids) > 1
        else 0
    )
    dev_groups = set(group_ids[:dev_group_count])
    result = []
    for record in records:
        item = dict(record)
        item["split"] = "internal_dev" if item["image_group_id"] in dev_groups else "internal_train"
        item["split_provenance"] = f"team-created seed={seed} fraction={validation_fraction:g}"
        result.append(item)
    return result


def find_cross_split_duplicate_groups(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Return content hashes assigned to more than one split."""
    assignments = defaultdict(set)
    for record in records:
        if record.get("image_group_id") and record.get("split"):
            if not str(record["split"]).startswith("excluded_"):
                assignments[record["image_group_id"]].add(record["split"])
    return {
        group_id: sorted(splits)
        for group_id, splits in assignments.items()
        if len(splits) > 1
    }
