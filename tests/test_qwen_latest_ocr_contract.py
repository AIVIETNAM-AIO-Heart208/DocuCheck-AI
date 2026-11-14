"""Latest OCR metadata and raw/merged evidence contracts; not inference tests."""

from copy import deepcopy

import pytest

from docucheck.extraction.ocr_contract import validate_runtime
from docucheck.extraction.qwen import adapt


def runtime():
    return {"pipeline":"phocr-detector-vietocr", "detector_device":"cuda:0",
            "recognizer_device":"cuda:0", "preprocessing": {
                "recognizer":{"scale_factor":2,"resampling":"LANCZOS"},
                "crop":{"padding_percent":10,"padding_fallback_percent":0,
                        "padding_fallback_candidates":0}},
            "postprocessing":{"mode":"post-ocr-horizontal-padding-collision",
                              "recognizer_reinvoked":False}}


def test_latest_runtime_accepted_and_old_scale_rejected():
    current = runtime()
    validate_runtime(current)
    old = deepcopy(current)
    old["preprocessing"]["recognizer"]["scale_factor"] = 1
    with pytest.raises(ValueError,match="outdated"):
        validate_runtime(old)
    old = deepcopy(current)
    del old["postprocessing"]
    with pytest.raises(ValueError):
        validate_runtime(old)


def test_merge_hint_keeps_raw_polygons_and_ids_without_duplicate_evidence():
    row = {"image_id":"test","status":"ok", "predictions":[
        {"candidate_id":"a","text":"THỨC","polygon":[[0,5],[35,0],[35,15],[0,20]]},
        {"candidate_id":"b","text":"COFFEE","polygon":[[40,0],[90,0],[90,15],[40,15]]}],
        "merged_predictions":[{"candidate_id":"merged","source_candidate_ids":["a","b"],
                               "text":"THỨC COFFEE"}]}
    original = deepcopy(row)
    result = adapt(row,100,100)
    assert len(result["regions"]) == 2
    assert len(result["ocr_merge_hints"]) == 1
    hint = result["ocr_merge_hints"][0]
    assert " ".join(result["mapping"][k]["text"] for k in hint["region_ids"]) == "THỨC COFFEE"
    assert result["mapping"][hint["region_ids"][0]]["polygon"] == row["predictions"][0]["polygon"]
    assert row == original
    row["merged_predictions"][0]["text"] = "invented"
    invalid = adapt(row,100,100)
    assert not invalid["ocr_merge_hints"]
    assert invalid["excluded_ocr_merges"][0]["reason"] == "merge_text_source_mismatch"


def test_empty_merge_list_is_valid_and_missing_members_are_not_invented():
    row = {"image_id":"test","status":"ok","predictions":[],"merged_predictions":[]}
    assert adapt(row,100,100)["ocr_merge_hints"] == []
    row["merged_predictions"] = [{"source_candidate_ids":["missing","other"],"text":"x"}]
    assert adapt(row,100,100)["excluded_ocr_merges"]
