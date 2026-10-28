import hashlib

import numpy as np
import pytest
from PIL import Image, ImageDraw

from docucheck.data.duplicates import audit_near_duplicates, perceptual_hash


def test_resize_compression_candidates_and_unrelated_image(tmp_path):
    image = Image.new("RGB", (400, 600), "white")
    draw = ImageDraw.Draw(image)
    for y in range(40, 550, 30):
        draw.rectangle((30, y, 150 + y % 160, y + 8), fill="black")
    image.save(tmp_path / "original.png")
    image.resize((200, 300)).save(tmp_path / "compressed.jpg", quality=60)
    rng = np.random.default_rng(42)
    Image.fromarray(rng.integers(0, 256, (600, 400), dtype=np.uint8)).save(tmp_path / "unrelated.png")
    assert (perceptual_hash(tmp_path / "original.png") ^ perceptual_hash(tmp_path / "compressed.jpg")).bit_count() <= 6
    assert (perceptual_hash(tmp_path / "original.png") ^ perceptual_hash(tmp_path / "unrelated.png")).bit_count() > 6
    records = [{"image_id": name, "image_path": name, "split": split,
                "checksum_sha256": hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()}
               for name, split in [("original.png", "internal_train"), ("compressed.jpg", "internal_dev"),
                                   ("unrelated.png", "official_validation_inventory")]]
    original = [dict(r) for r in records]
    candidates, summary, failures = audit_near_duplicates(records, tmp_path)
    assert len(candidates) == 1 and summary["candidate_count"] == 1
    assert not failures and records == original
    assert sum(summary["comparisons_by_split_pair"].values()) == 3
    assert audit_near_duplicates(list(reversed(records)), tmp_path) == (candidates, summary, failures)


def test_exact_matches_and_unreadable_images_are_reported_separately(tmp_path):
    Image.new("RGB", (40, 60), "white").save(tmp_path / "a.png")
    records = [{"image_id": str(i), "image_path": "a.png", "split": split, "checksum_sha256": "same"}
               for i, split in enumerate(("internal_train", "official_validation_inventory"))]
    records.append({"image_id": "missing", "image_path": "missing.png", "split": "internal_dev"})
    candidates, summary, failures = audit_near_duplicates(records, tmp_path)
    assert candidates == []
    assert sum(summary["exact_matches_by_split_pair"].values()) == 1
    assert summary["failed_images"] == len(failures) == 1


@pytest.mark.parametrize("threshold", [-1, 64, 1.5, True])
def test_invalid_threshold(threshold, tmp_path):
    with pytest.raises(ValueError):
        audit_near_duplicates([], tmp_path, threshold=threshold)
