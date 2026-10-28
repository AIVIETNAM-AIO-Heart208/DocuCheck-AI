"""Optional perceptual candidate audit; never changes records or split assignments."""

from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from docucheck.data.validation import is_relative_dataset_path


def perceptual_hash(path: str | Path) -> int:
    """63 AC bits from an 8x8 low-frequency DCT of a 32x32 grayscale image.

    DC is excluded. Hamming distance is a similarity heuristic, not evidence
    of transaction identity. Uniform/layout-similar images can collide.
    """
    with Image.open(path) as image:
        gray = image.convert("L").resize((32, 32), Image.Resampling.LANCZOS)
        coefficients = cv2.dct(np.asarray(gray, dtype=np.float32))[:8, :8].ravel()[1:]
    bits = coefficients > np.median(coefficients)
    return sum(int(bit) << index for index, bit in enumerate(bits))


def audit_near_duplicates(records, dataset_root, *, threshold=6):
    """Compare internal train/dev and both internal splits/official inventory.

    Exact SHA-256 matches are counted separately and omitted from candidates.
    O(n^2) comparisons suit the Week 1 receipt inventory, not large corpora.
    """
    if isinstance(threshold, bool) or not isinstance(threshold, int) or not 0 <= threshold <= 63:
        raise ValueError("threshold must be an integer between 0 and 63")
    split_pairs = {
        frozenset(("internal_train", "internal_dev")),
        frozenset(("internal_train", "official_validation_inventory")),
        frozenset(("internal_dev", "official_validation_inventory")),
    }
    allowed = set().union(*split_pairs)
    hashed, failures = [], []
    for record in sorted(records, key=lambda row: row["image_id"]):
        if record.get("split") not in allowed:
            continue
        try:
            if not is_relative_dataset_path(record.get("image_path")):
                raise ValueError("invalid relative path")
            fingerprint = perceptual_hash(Path(dataset_root) / record["image_path"])
            hashed.append((record, fingerprint))
        except (OSError, ValueError) as error:
            failures.append({"image_id": record["image_id"], "error_type": type(error).__name__})
    candidates, comparisons, exact = [], Counter(), Counter()
    for index, (left, left_hash) in enumerate(hashed):
        for right, right_hash in hashed[index + 1:]:
            if frozenset((left["split"], right["split"])) not in split_pairs:
                continue
            pair_name = " / ".join(sorted((left["split"], right["split"])))
            comparisons[pair_name] += 1
            if left.get("checksum_sha256") and left["checksum_sha256"] == right.get("checksum_sha256"):
                exact[pair_name] += 1
                continue
            distance = (left_hash ^ right_hash).bit_count()
            if distance <= threshold:
                candidates.append({
                    "left_image_id": left["image_id"], "right_image_id": right["image_id"],
                    "left_image_path": left["image_path"], "right_image_path": right["image_path"],
                    "split_pair": pair_name, "hamming_distance": distance,
                    "review_status": "not_reviewed",
                })
    candidates.sort(key=lambda row: (row["hamming_distance"], row["left_image_id"], row["right_image_id"]))
    return candidates, {
        "method": "grayscale 32x32 DCT, 8x8 low frequencies, 63 AC median bits",
        "threshold": threshold, "hashed_images": len(hashed), "failed_images": len(failures),
        "comparisons_by_split_pair": dict(sorted(comparisons.items())),
        "exact_matches_by_split_pair": dict(sorted(exact.items())),
        "candidate_count": len(candidates),
        "candidates_by_split_pair": dict(sorted(Counter(r["split_pair"] for r in candidates).items())),
        "interpretation": "Candidates only; layout similarity is not transaction identity. No split changes.",
    }, failures
