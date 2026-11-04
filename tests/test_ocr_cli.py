import json

from scripts import evaluate_ocr as cli


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_crop_mode_writes_crop_artifacts_only(tmp_path, capsys):
    manifest = tmp_path / "manifest.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    output = tmp_path / "evaluation"
    _write_jsonl(manifest, [{
        "image_id": "crop-1", "split": "official_val", "image_status": "valid",
        "text_status": "present", "text_raw": "CỬA HÀNG",
    }])
    _write_jsonl(predictions, [{
        "image_id": "crop-1", "split": "official_val", "status": "ok",
        "predictions": [{"text": "CỬA"}, {"text": "HÀNG"}],
    }])

    assert cli.main([
        "--mode", "crop", "--manifest", str(manifest), "--predictions", str(predictions),
        "--split", "official_val", "--output-dir", str(output),
    ]) == 0
    assert (output / "metrics.json").is_file()
    assert (output / "per_crop_metrics.jsonl").is_file()
    assert not (output / "per_image_metrics.jsonl").exists()
    assert '"split_role": "benchmark"' in capsys.readouterr().out


def test_full_page_mode_keeps_existing_artifact_names(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    output = tmp_path / "evaluation"
    polygon = [[0, 0], [20, 0], [20, 10], [0, 10]]
    _write_jsonl(manifest, [{
        "image_id": "receipt-1", "split": "internal_dev", "ocr_ground_truth_status": "available",
        "ocr_regions": [{"text_raw": "MẪU", "polygon": polygon, "validation_issues": []}],
    }])
    _write_jsonl(predictions, [{
        "image_id": "receipt-1", "split": "internal_dev", "status": "ok",
        "predictions": [{"text": "MẪU", "polygon": polygon}],
    }])

    assert cli.main([
        "--manifest", str(manifest), "--predictions", str(predictions),
        "--output-dir", str(output),
    ]) == 0
    assert (output / "per_image_metrics.jsonl").is_file()
    assert (output / "per_region_alignment.jsonl").is_file()
    assert not (output / "per_crop_metrics.jsonl").exists()
