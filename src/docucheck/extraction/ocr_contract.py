"""Latest receipt OCR contract and lossless merge-hint adapter; no inference."""

PROFILE = "phocr-vietocr-e1-guarded-padding-merge-v1"


def validate_runtime(runtime: dict) -> None:
    """Refuse stale OCR cache before starting the Qwen GPU server."""
    preprocessing = runtime.get("preprocessing", {})
    recognizer = preprocessing.get("recognizer", {})
    crop = preprocessing.get("crop", {})
    post = runtime.get("postprocessing", {})
    if not (
        runtime.get("pipeline") == "phocr-detector-vietocr"
        and runtime.get("detector_device") == "cuda:0"
        and runtime.get("recognizer_device") == "cuda:0"
        and recognizer.get("scale_factor") == 2
        and recognizer.get("resampling") == "LANCZOS"
        and crop.get("padding_percent") == 10
        and crop.get("padding_fallback_percent") == 0
        and "padding_fallback_candidates" in crop
        and post.get("mode") == "post-ocr-horizontal-padding-collision"
        and post.get("recognizer_reinvoked") is False
    ):
        raise ValueError("OCR cache/profile is outdated or incompatible: expected " + PROFILE
                         + ". Run fresh OCR without --reuse-ocr.")


def merge_hints(row: dict, mapping: dict) -> tuple[list, list]:
    """Use raw member polygons as evidence, never a union box as a text baseline.

    Incoming merge order/text stays an advisory hypothesis: its vertical-overlap
    grouping can span different physical lines in a tilted receipt.
    """
    source_to_region = {r["source_candidate_id"]: key for key, r in mapping.items()}
    accepted, excluded = [], []
    for merged in row.get("merged_predictions", []):
        if not isinstance(merged, dict):
            excluded.append({"reason": "invalid_merge_record"})
            continue
        members = merged.get("source_candidate_ids")
        if (not isinstance(members, list) or len(members) < 2
                or any(not isinstance(k, str) or k not in source_to_region for k in members)
                or len(set(members)) != len(members)):
            excluded.append({"candidate_id": merged.get("candidate_id"), "reason": "invalid_or_missing_merge_sources"})
            continue
        ids = [source_to_region[k] for k in members]
        expected = " ".join(mapping[k]["text"] for k in ids if mapping[k]["text"])
        if merged.get("text") != expected:
            excluded.append({"candidate_id": merged.get("candidate_id"), "reason": "merge_text_source_mismatch"})
            continue
        accepted.append({"source_candidate_id": merged.get("candidate_id"),
                         "region_ids": ids, "text": expected,
                         "verified_entity": False, "advisory_only": True})
    return accepted, excluded
