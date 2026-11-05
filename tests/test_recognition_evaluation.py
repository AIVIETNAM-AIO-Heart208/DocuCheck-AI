"""Recognition protocol regressions with hand-calculated expected scores."""

import pytest

from docucheck.evaluation.metrics import cer, wer, evaluate_crop_records


def crop(image_id, text, **extra):
    return {"image_id": image_id, "split": "official_val", "image_status": "valid",
            "text_status": "present", "text_raw": text, **extra}


def prediction(image_id, text):
    return {"image_id": image_id, "split": "official_val", "status": "ok",
            "predictions": [{"text": text}] if text else []}


@pytest.mark.parametrize("reference,hypothesis,expected", [
    ("ab", "ac", (1, 2)), ("ab", "a", (1, 2)), ("ab", "abc", (1, 2)),
    ("", "", (0, 0)), ("", "abc", (3, 0)), ("abc", "", (3, 3)),
    ("a", "abcd", (3, 1)), ("CỬA", "CU\u031b\u0309A", (0, 3)),
])
def test_character_edits_and_unicode(reference, hypothesis, expected):
    assert cer(reference, hypothesis) == expected


def test_micro_averaging_uses_total_denominators_and_normalized_exact_match():
    # First sample: 1/1 character error; second: 0/9. Micro CER=1/10, not 1/2.
    rows = [crop("a", "a"), crop("b", "  CỬA  HÀNG! ")]
    predictions = [prediction("b", "cửa hàng!"), prediction("a", "b")]
    summary, details = evaluate_crop_records(rows, predictions, split="official_val")
    assert summary["character_errors"] == 1
    assert summary["ground_truth_characters"] == 10
    assert summary["cer"] == pytest.approx(0.1)
    assert summary["wer"] == pytest.approx(1 / 3)
    assert summary["exact_match_rate"] == 0.5
    assert summary["exact_match_crops"] == 1
    assert [r["exact_match"] for r in details] == [False, True]
    assert summary["eligible_prediction_coverage"] == 1


def test_exclusions_have_explicit_disjoint_counts_and_empty_output_is_scored():
    rows = [crop("ok", "xin chào"), crop("blank", " \t"),
            crop("missing", None), crop("image", "text", image_status="invalid"),
            crop("status", "text", text_status="invalid")]
    summary, details = evaluate_crop_records(rows, [prediction("ok", "")], split="official_val")
    assert summary["manifest_crops"] == 5
    assert summary["evaluated_crops"] == 1
    assert summary["excluded_crops"] == 4
    assert set(summary["exclusion_counts"].values()) == {1}
    assert summary["manifest_evaluation_coverage"] == 0.2
    assert summary["empty_hypothesis_crops"] == 1
    assert summary["cer"] == summary["wer"] == 1
    assert summary["exact_match_rate"] == 0


@pytest.mark.parametrize("cross_split", [False, True])
def test_duplicate_manifest_ids_are_rejected_before_dict_conversion(cross_split):
    rows = [crop("a", "a"), crop("a", "a", split="official_train" if cross_split else "official_val")]
    with pytest.raises(ValueError, match="duplicate crop manifest"):
        evaluate_crop_records(rows, [prediction("a", "a")], split="official_val")


def test_duplicate_and_unknown_predictions_are_rejected():
    rows = [crop("a", "a")]
    with pytest.raises(ValueError, match="duplicate crop prediction"):
        evaluate_crop_records(rows, [prediction("a", "a")] * 2, split="official_val")
    with pytest.raises(ValueError, match="Unknown crop prediction"):
        evaluate_crop_records(rows, [prediction("other", "a")], split="official_val")


def test_partial_success_never_produces_a_benchmark():
    with pytest.raises(ValueError, match="Missing or failed OCR predictions for 1 crops"):
        evaluate_crop_records([crop("a", "a"), crop("b", "b")], [prediction("a", "a")], split="official_val")


def test_all_empty_references_are_rejected_and_wer_keeps_reference_denominator():
    with pytest.raises(ValueError, match="No valid crop transcripts"):
        evaluate_crop_records([crop("a", "")], [prediction("a", "")], split="official_val")
    assert wer("a", "a b c") == (2, 1)
