from scripts.verify_recognition_benchmark import matches_locked_source


def test_document_revision_requires_both_original_and_current_hashes():
    name = "docs/protocol.md"
    revision = {name: {"original_sha256": "old", "revised_sha256": "new"}}
    assert matches_locked_source(name, "old", "old", {})
    assert matches_locked_source(name, "new", "old", revision)
    assert not matches_locked_source(name, "new", "old", {})
    assert not matches_locked_source(name, "unexpected", "old", revision)
    assert not matches_locked_source(name, "new", "another-original", revision)


def test_document_revision_cannot_exempt_changed_executable_code():
    for name in ("src/docucheck/evaluation/metrics.py", "scripts/evaluate_ocr.py", "docs/helper.py"):
        revision = {name: {"original_sha256": "old", "revised_sha256": "new"}}
        assert not matches_locked_source(name, "new", "old", revision)
