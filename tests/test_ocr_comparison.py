import json

import pytest

from docucheck.evaluation.comparison import compare_crop_runs, write_comparison
from scripts import compare_ocr_engines as cli


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _run(tmp_path, name, *, cer=0.1, image_id="crop-1", failures=0, chars=10):
    root = tmp_path / name
    root.mkdir()
    (root / "runtime.json").write_text(json.dumps({
        "engine": name.title(), "engine_version": "1", "model_names": {"recognition": "model"},
        "model_source": "official", "model_sha256": "hash", "device": "cpu", "split": "official_val",
        "images_succeeded": 1, "images_failed": failures, "mean_successful_image_latency_seconds": 0.1,
    }), encoding="utf-8")
    (root / "metrics.json").write_text(json.dumps({
        "split": "official_val", "evaluated_crops": 1, "cer": cer, "character_errors": 1,
        "ground_truth_characters": chars, "wer": 0.5, "word_errors": 1, "ground_truth_words": 2,
        "empty_hypothesis_crops": 0, "text_normalization_policy": "policy",
    }), encoding="utf-8")
    _write_jsonl(root / "per_crop_metrics.jsonl", [{
        "image_id": image_id, "text_gt": "MẪU", "text_pred": name, "char_errors": 1,
        "gt_characters": chars, "cer": cer, "word_errors": 1, "gt_words": 2, "wer": 0.5,
    }])
    return root


def test_comparison_orders_by_cer_and_keeps_all_hypotheses(tmp_path):
    paths = {
        "tesseract": _run(tmp_path, "tesseract", cer=0.3),
        "vietocr": _run(tmp_path, "vietocr", cer=0.1),
        "paddleocr": _run(tmp_path, "paddleocr", cer=0.2),
    }
    summary, details = compare_crop_runs(paths)
    assert [row["engine_key"] for row in summary["engines"]] == ["vietocr", "paddleocr", "tesseract"]
    assert set(details[0]["engines"]) == set(paths)
    assert details[0]["disagreement"] is True
    write_comparison(tmp_path / "out", summary, details)
    assert (tmp_path / "out/comparison.json").is_file()


@pytest.mark.parametrize("change, match", [
    ({"failures": 1}, "incomplete"),
    ({"image_id": "different"}, "ID sets"),
    ({"chars": 11}, "denominators"),
])
def test_comparison_rejects_incomparable_runs(tmp_path, change, match):
    paths = {name: _run(tmp_path, name, **(change if name == "paddleocr" else {}))
             for name in ("tesseract", "vietocr", "paddleocr")}
    with pytest.raises(ValueError, match=match):
        compare_crop_runs(paths)


def test_comparison_cli_writes_artifacts(tmp_path):
    paths = {name: _run(tmp_path, name) for name in ("tesseract", "vietocr", "paddleocr")}
    output = tmp_path / "comparison"
    assert cli.main([
        "--tesseract", str(paths["tesseract"]), "--vietocr", str(paths["vietocr"]),
        "--paddleocr", str(paths["paddleocr"]), "--output-dir", str(output),
    ]) == 0
    assert (output / "comparison.json").is_file()
    assert (output / "per_crop_comparison.jsonl").is_file()
