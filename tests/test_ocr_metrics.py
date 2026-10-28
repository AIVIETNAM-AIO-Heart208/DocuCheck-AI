import pytest

from docucheck.evaluation.metrics import (
    align_word_predictions_to_lines,
    cer,
    detection_scores,
    evaluate_ocr_records,
    greedy_polygon_matching,
    normalize_text,
    wer,
)
from docucheck.ocr.baseline import parse_tesseract_tsv


def _box(x1, y1, x2, y2, **extra):
    return {"polygon": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]], **extra}


def test_unicode_normalization_preserves_vietnamese_diacritics():
    assert normalize_text("  CỬA   HÀNG  ") == "cửa hàng"
    assert cer("CỬA", "cửa") == (0, 3)
    assert cer("CỬA", "CUA")[0] > 0


def test_wer_uses_whitespace_tokens_and_handles_empty_reference():
    assert wer("cửa hàng", "cửa quán") == (1, 2)
    assert wer("", "extra words") == (2, 0)


def test_iou_matching_reports_true_false_positive_and_missed_regions():
    predictions = [_box(0, 0, 10, 10), _box(30, 30, 40, 40)]
    ground_truth = [_box(0, 0, 10, 10, text_raw=""), _box(15, 15, 25, 25)]
    matching = greedy_polygon_matching(predictions, ground_truth, iou_threshold=0.5)
    assert matching["true_positives"] == 1
    assert matching["false_positives"] == 1
    assert matching["false_negatives"] == 1
    assert detection_scores(matching)["f1"] == 0.5


def test_empty_predictions_count_as_missed_regions():
    matching = greedy_polygon_matching([], [_box(1, 1, 5, 5)], iou_threshold=0.5)
    assert matching["false_positives"] == 0
    assert matching["false_negatives"] == 1
    aligned, unmatched = align_word_predictions_to_lines([], [_box(1, 1, 5, 5, text_raw="Xin chào")])
    assert aligned[0]["text_pred"] == ""
    assert aligned[0]["matched"] is False
    assert unmatched == []


def test_unicode_alignment_counts_insertions_and_unassigned_predictions():
    gt = [_box(0, 0, 50, 15, text_raw="CỬA HÀNG MẪU", validation_issues=[])]
    predictions = [
        {"text": "CỬA", **_box(2, 2, 15, 12)},
        {"text": "HÀNG", **_box(17, 2, 32, 12)},
        {"text": "MẪU", **_box(35, 2, 45, 12)},
        {"text": "SPURIOUS", **_box(100, 100, 120, 120)},
    ]
    aligned, unmatched = align_word_predictions_to_lines(predictions, gt)
    assert aligned[0]["text_pred"] == "CỬA HÀNG MẪU"
    assert unmatched == [3]


def test_evaluation_reports_unicode_cer_wer_and_n_a_detection():
    manifest = [{
        "image_id": "receipt-1",
        "split": "internal_dev",
        "image_width": 100,
        "image_height": 40,
        "ocr_ground_truth_status": "available",
        "ocr_regions": [_box(0, 0, 50, 15, text_raw="CỬA HÀNG", validation_issues=[])],
    }]
    predictions = [{
        "image_id": "receipt-1",
        "split": "internal_dev",
        "status": "ok",
        "predictions": [{"text": "CỬA", **_box(2, 2, 15, 12)}, {"text": "HÀNG", **_box(17, 2, 32, 12)}],
    }]
    summary, images, regions = evaluate_ocr_records(manifest, predictions, split="internal_dev")
    assert summary["cer"] == 0
    assert summary["wer"] == 0
    assert summary["evaluated_ground_truth_regions"] == 1
    assert summary["detection_metrics"]["status"].startswith("N/A")
    assert images[0]["cer"] == 0
    assert regions[0]["text_pred"] == "CỬA HÀNG"


def test_evaluation_rejects_missing_or_failed_predictions():
    manifest = [{
        "image_id": "receipt-1",
        "split": "internal_dev",
        "ocr_ground_truth_status": "available",
        "ocr_regions": [_box(0, 0, 50, 15, text_raw="CỬA HÀNG", validation_issues=[])],
    }]
    with pytest.raises(ValueError, match="Missing or failed OCR predictions"):
        evaluate_ocr_records(manifest, [], split="internal_dev")
    failed = [{"image_id": "receipt-1", "split": "internal_dev", "status": "error"}]
    with pytest.raises(ValueError, match="Missing or failed OCR predictions"):
        evaluate_ocr_records(manifest, failed, split="internal_dev")
    malformed = [{"image_id": "receipt-1", "split": "internal_dev", "status": "ok"}]
    with pytest.raises(ValueError, match="Missing or failed OCR predictions"):
        evaluate_ocr_records(manifest, malformed, split="internal_dev")


def test_successful_zero_word_result_counts_as_evaluated_ocr():
    manifest = [{
        "image_id": "receipt-1",
        "split": "internal_dev",
        "ocr_ground_truth_status": "available",
        "ocr_regions": [_box(0, 0, 50, 15, text_raw="CỬA HÀNG", validation_issues=[])],
    }]
    predictions = [{"image_id": "receipt-1", "split": "internal_dev", "status": "ok", "predictions": []}]
    summary, images, _ = evaluate_ocr_records(manifest, predictions, split="internal_dev")
    assert summary["images_with_ground_truth_and_predictions"] == 1
    assert summary["unmatched_ground_truth_regions"] == 1
    assert images[0]["cer"] == 1.0


def test_tesseract_tsv_parser_skips_continuation_fragments_and_bounds_text():
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t10\t20\t30\t12\t90.0\tCỬA\n"
        "corrupt continuation with no numeric geometry\n"
        "5\t1\t1\t1\t1\t2\t45\t20\t35\t12\t80.0\tHÀNG\n"
    )
    rows = parse_tesseract_tsv(tsv)
    assert [row["text"] for row in rows] == ["CỬA", "HÀNG"]
    assert len(rows) == 2
