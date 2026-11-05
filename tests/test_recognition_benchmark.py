"""Audit failures that must prevent a misleading clean benchmark."""
import hashlib

from PIL import Image

from scripts.run_recognition_benchmark import audit


def record(root, name, split, color):
    path = root / name
    Image.new("RGB", (30, 12), color).save(path)
    return {"image_id": name, "image_path": name, "split": split,
            "image_status": "valid", "text_status": "present", "text_raw": "Mẫu",
            "image_width": 30, "image_height": 12,
            "checksum_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def test_audit_decodes_source_pixels_and_detects_stale_manifest(tmp_path):
    rows = [record(tmp_path, "one.png", "official_train", "white"),
            record(tmp_path, "two.png", "official_val", "black")]
    summary = audit(rows, tmp_path, tmp_path)
    assert summary["decoded_and_verified_images"] == 2
    assert summary["cross_split_exact_duplicate_groups"] == 0
    Image.new("RGB", (31, 12), "red").save(tmp_path / "one.png")
    (tmp_path / "two.png").write_bytes(b"broken image")
    summary = audit(rows, tmp_path, tmp_path)
    assert summary["invalid_records"] == 2
    assert summary["decoded_and_verified_images"] == 0
    assert summary["issue_counts"]["checksum_mismatch"] == 1
    assert summary["issue_counts"]["dimension_mismatch"] == 1


def test_distinct_ids_do_not_hide_exact_image_leakage(tmp_path):
    rows = [record(tmp_path, "train.png", "official_train", "white"),
            record(tmp_path, "val.png", "official_val", "white")]
    summary = audit(rows, tmp_path, tmp_path)
    assert summary["unique_ids"] == 2
    assert summary["invalid_records"] == 0
    assert summary["cross_split_exact_duplicate_groups"] == 1
