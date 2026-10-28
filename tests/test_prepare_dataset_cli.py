import json
from pathlib import Path

import pytest

from scripts import prepare_dataset as cli
from test_preprocessing import _write_dataset


ARTIFACTS = (
    "manifest.jsonl", "recognition_manifest.jsonl",
    "validation_report.json", "split_summary.json",
)


def _run(root, output, *options):
    return cli.main(["--dataset-root", str(root), "--output-dir", str(output), *options])


def _bytes(output):
    return {name: (output / name).read_bytes() for name in ARTIFACTS}


def test_fail_diagnostics_preserve_requested_policy_and_previous_bundle(tmp_path, capsys):
    root, output = tmp_path / "source", tmp_path / "output"
    _write_dataset(root, invalid_geometry=True)
    assert _run(root, output) == 0
    previous = _bytes(output)
    assert _run(root, output, "--invalid-policy", "fail") == 2
    assert _bytes(output) == previous
    diagnostic = json.loads((output / "validation_failure_report.json").read_text(encoding="utf-8"))
    assert diagnostic["invalid_policy"] == "fail"
    assert diagnostic["invalid_record_count"] == 2
    assert "validation_failure_report.json" in capsys.readouterr().err


def test_cli_reproducible_strict_bundle_and_detects_mixed_artifacts(tmp_path):
    root = tmp_path / "source"
    _write_dataset(root)
    first, second = tmp_path / "first", tmp_path / "second"
    assert _run(root, first) == _run(root, second) == 0
    assert _bytes(first) == _bytes(second)
    assert cli.main(["--output-dir", str(first), "--verify-only"]) == 0
    (first / "recognition_manifest.jsonl").write_text("{}\n", encoding="utf-8")
    assert cli.main(["--output-dir", str(first), "--verify-only"]) == 2


@pytest.mark.parametrize("policy", ["report", "skip", "fail"])
def test_all_policies_publish_valid_source_with_requested_policy(tmp_path, policy):
    root, output = tmp_path / "source", tmp_path / "output"
    _write_dataset(root)
    assert _run(root, output, "--invalid-policy", policy) == 0
    report = json.loads((output / "validation_report.json").read_text(encoding="utf-8"))
    assert report["invalid_policy"] == policy
    assert report["invalid_record_count"] == report["invalid_recognition_record_count"] == 0
    assert cli.main(["--output-dir", str(output), "--verify-only"]) == 0


def test_verify_rejects_malformed_report_and_inconsistent_counts(tmp_path):
    root, output = tmp_path / "source", tmp_path / "output"
    _write_dataset(root)
    assert _run(root, output) == 0
    path = output / "validation_report.json"
    original = json.loads(path.read_text(encoding="utf-8"))
    for malformed in ([], dict(original, records_by_split={}), dict(original, output_statistics=None)):
        path.write_text(json.dumps(malformed), encoding="utf-8")
        assert cli.main(["--output-dir", str(output), "--verify-only"]) == 2


@pytest.mark.parametrize("failure", ["serialization", *ARTIFACTS])
def test_output_failure_preserves_all_previous_artifacts(tmp_path, monkeypatch, failure):
    root, output = tmp_path / "source", tmp_path / "output"
    _write_dataset(root)
    assert _run(root, output) == 0
    previous = _bytes(output)
    if failure == "serialization":
        original = cli.write_jsonl

        def broken_write(path, records):
            if Path(path).name == "recognition_manifest.jsonl":
                raise OSError("injected write failure")
            original(path, records)

        monkeypatch.setattr(cli, "write_jsonl", broken_write)
    else:
        original = Path.replace
        failed = False

        def broken_replace(path, target):
            nonlocal failed
            if Path(target) == output / failure and not failed:
                failed = True
                raise OSError("injected publish failure")
            return original(path, target)

        monkeypatch.setattr(Path, "replace", broken_replace)
    assert _run(root, output, "--seed", "17") == 2
    assert _bytes(output) == previous
    assert cli.main(["--output-dir", str(output), "--verify-only"]) == 0


def test_fail_without_previous_output_does_not_publish_success_files(tmp_path):
    root, output = tmp_path / "source", tmp_path / "output"
    _write_dataset(root, invalid_geometry=True)
    assert _run(root, output, "--invalid-policy", "fail") == 2
    assert not any((output / name).exists() for name in ARTIFACTS)


def test_fail_collects_recognition_errors_even_with_receipt_errors(tmp_path):
    root, output = tmp_path / "source", tmp_path / "output"
    _write_dataset(root, invalid_geometry=True)
    (root / "text_recognition_train_data.txt").write_text("missing.jpg\t\n", encoding="utf-8")
    assert _run(root, output, "--invalid-policy", "fail") == 2
    report = json.loads((output / "validation_failure_report.json").read_text(encoding="utf-8"))
    assert report["invalid_policy"] == "fail"
    assert report["invalid_record_count"] == 2
    assert report["invalid_recognition_record_count"] == 1
    assert report["recognition_missing_crop_count"] == 1


def test_structural_rejection_keeps_previous_success_bundle(tmp_path, monkeypatch):
    root, output = tmp_path / "source", tmp_path / "output"
    _write_dataset(root)
    assert _run(root, output) == 0
    previous = _bytes(output)
    original = cli.prepare_records

    def broken_prepare(*args, **kwargs):
        records, crops, report = original(*args, **kwargs)
        records[0]["split"] = "invalid_split"
        return records, crops, report

    monkeypatch.setattr(cli, "prepare_records", broken_prepare)
    assert _run(root, output) == 2
    assert _bytes(output) == previous


def test_cli_skip_summary_counts_retained_records_and_duplicates(tmp_path):
    root, output = tmp_path / "source", tmp_path / "output"
    _write_dataset(root, invalid_geometry=True)
    assert _run(root, output, "--invalid-policy", "skip") == 0
    report = json.loads((output / "validation_report.json").read_text(encoding="utf-8"))
    summary = json.loads((output / "split_summary.json").read_text(encoding="utf-8"))
    assert report["source_statistics"]["receipt_record_count"] == 4
    assert report["output_statistics"]["receipt_record_count"] == 2
    assert report["skipped_record_count"] == 2
    assert summary["exact_duplicate_groups"] == 0
    assert sum(summary["records_by_split"].values()) == 2
    assert cli.main(["--output-dir", str(output), "--verify-only"]) == 0


def test_nonfinite_source_geometry_survives_strict_serialization_and_staged_validation(tmp_path):
    root, output = tmp_path / "source", tmp_path / "output"
    _write_dataset(root)
    directory = root / "kie_data/kie_data/boxes_and_transcripts"
    directory.mkdir(parents=True)
    raw = "0,nan,2,20,2,20,12,1,12,,Nguyên văn"
    (directory / "receipt_a.tsv").write_text(raw, encoding="utf-8")
    assert _run(root, output) == 0
    rows = [json.loads(line) for line in (output / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    region = next(r for r in rows if r["source_image_name"] == "receipt_a.jpg")["ocr_regions"][0]
    assert region["validation_issues"] == ["non_finite_coordinates"]
    assert region["polygon"][0][0] == "nan" and region["bbox_xyxy"] is None
    assert region["source_raw"] == raw
    assert cli.main(["--output-dir", str(output), "--verify-only"]) == 0


def test_failed_first_publish_removes_partial_new_artifacts(tmp_path, monkeypatch):
    root, output = tmp_path / "source", tmp_path / "output"
    _write_dataset(root)
    original = Path.replace

    def broken_replace(path, target):
        if Path(target) == output / "split_summary.json":
            raise OSError("injected first-run publish failure")
        return original(path, target)

    monkeypatch.setattr(Path, "replace", broken_replace)
    assert _run(root, output) == 2
    assert not any((output / name).exists() for name in ARTIFACTS)
