import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from scripts import run_ocr
from scripts.run_psm_comparison import audit, main as compare_main
from docucheck.evaluation.metrics import evaluate_ocr_records
from docucheck.ocr import baseline


@pytest.mark.parametrize("psm", [6, 4, 11])
def test_cli_psm_reaches_real_adapter_subprocess(tmp_path, monkeypatch, psm):
    Image.new("RGB", (30, 20), "white").save(tmp_path / "receipt.png")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"image_id": "r", "image_path": "receipt.png", "split": "internal_dev"}) + "\n")
    models = tmp_path / "model directory"
    models.mkdir()
    (models / "vie.traineddata").write_bytes(b"synthetic test model")
    executable = str(tmp_path / "Program Files" / "Tesseract-OCR" / "tesseract.exe")
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[1] == "--version":
            return SimpleNamespace(stdout="tesseract test\n", returncode=0)
        Path(command[2]).with_suffix(".tsv").write_text(
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t1\t1\t10\t10\t90\tMẪU\n", encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(baseline.subprocess, "run", run)
    output = tmp_path / "output"
    assert run_ocr.main(["--manifest", str(manifest), "--dataset-root", str(tmp_path),
        "--psm", str(psm), "--tesseract", executable, "--tessdata-dir", str(models),
        "--output-dir", str(output)]) == 0
    command = calls[-1]
    assert command[0] == executable
    assert command[command.index("--psm") + 1] == str(psm)
    assert command[command.index("--oem") + 1] == "1"
    assert command[command.index("--tessdata-dir") + 1] == str(models.resolve())
    assert json.loads((output / "runtime.json").read_text())["preprocessing"]["page_segmentation_mode"] == psm


@pytest.mark.parametrize("psm", ["-1", "14", "abc"])
def test_cli_rejects_invalid_psm(psm):
    with pytest.raises(SystemExit):
        run_ocr.build_parser().parse_args(["--psm", psm])


def rows():
    record = {"image_id": "r", "split": "internal_dev", "ocr_ground_truth_status": "available",
              "ocr_regions": [{"text_raw": "MẪU", "polygon": [[0, 0], [20, 0], [20, 20], [0, 20]]}]}
    prediction = {"image_id": "r", "split": "internal_dev", "status": "ok", "predictions": []}
    return record, prediction


@pytest.mark.parametrize("case", ["manifest_duplicate", "prediction_duplicate", "unknown", "wrong_split", "missing_id"])
def test_full_page_rejects_ambiguous_ids(case):
    r, p = rows()
    manifest, predictions = [r], [p]
    if case == "manifest_duplicate":
        manifest.append({**r, "split": "internal_train"})
    elif case == "prediction_duplicate":
        predictions.append(dict(p))
    elif case == "unknown":
        predictions.append({**p, "image_id": "other"})
    elif case == "wrong_split":
        predictions[0] = {**p, "split": "internal_train"}
    else:
        predictions[0] = {**p, "image_id": None}
    with pytest.raises(ValueError):
        evaluate_ocr_records(manifest, predictions, split="internal_dev")


def test_comparison_refuses_existing_evidence(tmp_path):
    (tmp_path / "evidence.txt").write_text("keep")
    with pytest.raises(SystemExit):
        compare_main(["--output-dir", str(tmp_path)])
    assert (tmp_path / "evidence.txt").read_text() == "keep"


def test_audit_rejects_changed_image_and_records_exclusion(tmp_path):
    import hashlib
    path = tmp_path / "receipt.png"
    Image.new("RGB", (20, 20), "white").save(path)
    r, _ = rows()
    r.update(image_path=path.name, image_width=20, image_height=20,
             checksum_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    r["ocr_regions"].append({"text_raw": "bad geometry", "polygon": [], "validation_issues": ["zero_area"]})
    result = audit([r], tmp_path, expected=1)
    assert result["evaluated_regions"] == 1
    assert result["excluded_regions"][0]["reason"] == "invalid_geometry"
    Image.new("RGB", (20, 20), "black").save(path)
    with pytest.raises(ValueError, match="identity mismatch"):
        audit([r], tmp_path, expected=1)


def test_review_selection_is_unique_deterministic_and_covers_both_directions():
    from scripts.review_psm_comparison import select_cases
    ids = [f"r{i:02d}" for i in range(30)]
    images = {p: {s: {"cer": 1.0 if p == 6 else (i / 30 if p == 4 else 1.5 - i / 30)}
                  for i, s in enumerate(ids)} for p in (6, 4, 11)}
    regions = {p: {s: [{"matched": p != 4}] for s in ids} for p in (6, 4, 11)}
    chosen = select_cases(images, regions)
    assert chosen == select_cases(images, regions)
    assert len(chosen) == len({r["image_id"] for r in chosen}) == 20
    groups = {r["selection_group"] for r in chosen}
    assert "psm11_largest_cer_improvement" in groups
    assert "psm11_largest_cer_regression" in groups
    assert all(r["review_status"] == "pending" and r["reviewer"] is None for r in chosen)


def test_evidence_inventory_detects_changed_and_added_artifacts(tmp_path):
    from scripts.verify_psm_evidence import inventory
    p = tmp_path / "predictions.jsonl"
    p.write_text("original")
    original = inventory(tmp_path)
    p.write_text("changed")
    assert inventory(tmp_path) != original
    p.write_text("original")
    (tmp_path / "extra.txt").write_text("extra")
    assert inventory(tmp_path) != original


@pytest.mark.parametrize("suffix,expected", [
    ("98,000,TOTAL_COST", "98,000"), (",OTHER", ""),
    ("Cửa hàng, Quảng Ninh,ADDRESS", "Cửa hàng, Quảng Ninh"), ("OTHER,OTHER", "OTHER"),
])
def test_full_page_source_schema_keeps_transcript_and_terminal_category_separate(suffix, expected):
    from docucheck.data.loader import parse_full_page_text_line
    raw = "1,0,0,20,0,20,20,0,20," + suffix
    row = parse_full_page_text_line(raw, 1)
    assert row["text_raw"] == expected
    assert row["source_category"] == suffix.rsplit(",", 1)[1]
    assert row["source_raw"] == raw and row["source_issue"] is None


def test_unknown_terminal_category_is_not_assumed_to_be_text():
    from docucheck.data.loader import parse_full_page_text_line
    row = parse_full_page_text_line("1,0,0,20,0,20,20,0,20,text,UNKNOWN", 1)
    assert row["text_raw"] is None
    assert row["source_issue"] == "unknown_terminal_category"


def test_partial_text_gt_keeps_geometry_coverage_separate():
    r, p = rows()
    r["ocr_ground_truth_status"] = "partial_transcriptions"
    r["ocr_regions"].append({"text_raw": "", "polygon": [[30, 0], [50, 0], [50, 20], [30, 20]]})
    p["predictions"] = [{"text": "untranscribed", "polygon": [[31, 1], [40, 1], [40, 10], [31, 10]]}]
    summary, images, regions = evaluate_ocr_records([r], [p], split="internal_dev")
    assert summary["evaluated_ground_truth_regions"] == 1
    assert summary["excluded_empty_transcription_regions"] == 1
    assert summary["cer"] == 1
    assert summary["unassigned_prediction_word_boxes"] == 1
    assert summary["geometry_coverage"]["valid_regions"] == 2
    assert summary["geometry_coverage"]["unassigned_word_boxes"] == 0
    assert summary["geometry_coverage"]["unmatched_regions"] == 1
    assert len(regions) == 1 and len(images) == 1


def test_corrected_manifest_preserves_identity_and_geometry_and_original(tmp_path):
    import copy
    from scripts.reevaluate_psm_comparison import corrected_records
    r, _ = rows()
    r.update(source_image_name="receipt.jpg", image_path="same.jpg", checksum_sha256="unchanged")
    raw = "1,0,0,20,0,20,20,0,20,98,000,TOTAL_COST"
    r["ocr_regions"][0].update(text_raw="000,TOTAL_COST", text_status="present", source_raw=raw,
                               source_line=1, validation_issues=[])
    folder = tmp_path / "kie_data/kie_data/boxes_and_transcripts"
    folder.mkdir(parents=True)
    (folder / "receipt.tsv").write_text(raw + "\n", encoding="utf-8")
    before = copy.deepcopy(r)
    revised, sources = corrected_records([r], tmp_path)
    assert r == before
    assert revised[0]["ocr_regions"][0]["text_raw"] == "98,000"
    assert revised[0]["ocr_regions"][0]["source_category"] == "TOTAL_COST"
    for key in ("image_id", "image_path", "split", "checksum_sha256"):
        assert revised[0][key] == before[key]
    assert revised[0]["ocr_regions"][0]["polygon"] == before["ocr_regions"][0]["polygon"]
    assert len(sources) == 1


def test_benchmark_audit_rejects_old_misparsed_category_gt(tmp_path):
    import hashlib
    path = tmp_path / "receipt.png"
    Image.new("RGB", (20, 20), "white").save(path)
    r, _ = rows()
    r.update(image_path=path.name, image_width=20, image_height=20,
             checksum_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    r["ocr_regions"][0].update(text_raw="OTHER", source_raw="1,0,0,20,0,20,20,0,20,Visible text,OTHER", source_line=1)
    with pytest.raises(ValueError, match="transcript source mismatch"):
        audit([r], tmp_path, expected=1)
