# Week 2 Handoff

## Ready to reuse

- `data/processed/manifest.jsonl` is the canonical local receipt/annotation manifest.
- `data/processed/recognition_manifest.jsonl` contains the separate official text-recognition crop/transcript pairs (5,285 train, 1,300 validation). It has no verified parent receipt or KIE field relationship; do not use these transcripts as KIE labels.
- `src/docucheck/data/loader.py`, `preprocessing.py`, `splitting.py`, and `validation.py` expose parsing, schema normalization, deterministic splits and validation without notebook execution.
- OCR predictions from `scripts/run_ocr.py` are word-level Tesseract boxes and can be loaded as JSONL; runtime details are stored beside them.
- `scripts/evaluate_ocr.py` and `src/docucheck/evaluation/metrics.py` provide reusable recognition metrics and documented alignment.

## Week 2 recommendations

1. Build KIE targets only from verified KIE labels; keep full-page OCR transcripts as a separate signal. Preserve the unmapped label anomaly for review.
2. Establish train/dev evaluation at receipt level and retain the existing duplicate quarantine. Do not tune on official test data.
3. Treat OCR output as uncertain evidence: preserve source boxes, confidence and provenance, and route unmatched or low-confidence regions for review.
4. Revisit annotation geometry before interpreting OCR metrics. Current GT regions are coarser than word boxes, and baseline CER/WER are alignment-sensitive; create a compatible validation protocol before comparing models.
5. Keep claims grounded in visible evidence. Numerical checks should indicate a review condition and must not imply fraud.
6. Regenerate manifests to schema 1.1. Use `annotation_issues`, raw source arrays/lines, text/label statuses and geometry issues together. Structural validation is not annotation correctness. Unique source IDs and real-data receipt splits are preserved; repeated source rows have distinct line-derived IDs.
7. Run `scripts/audit_dataset.py` and follow [the review protocol](ANNOTATION_AUDIT.md). Complete the 40-image review and inspect cross-split perceptual candidates before claiming annotation quality or absence of near-duplicate leakage. Keep official validation review limited to leakage investigation; do not use it for model tuning.

## Preparing and checking a reusable bundle

Create a separate local output directory when checking changes; keep the current `data/processed/` bundle available to existing consumers:

```bash
uv run python scripts/prepare_dataset.py --dataset-root data/mcocr --output-dir outputs/audit/my_preparation --seed 42 --validation-fraction 0.2 --invalid-policy report
uv run python scripts/prepare_dataset.py --output-dir outputs/audit/my_preparation --verify-only
```

Consume the receipt manifest, recognition manifest, validation report and split summary together. The report includes hashes of the other three artifacts; `--verify-only` checks hashes, strict JSON, structural metadata, split counts and output statistics. Existing bundles without these hashes need regeneration into a new directory. Current source/processed manifests were preserved during the 2026-10-28 hardening verification; the new receipt and recognition manifests were byte-identical to them.

`report` retains source-quality errors with accurate diagnostics. `skip` removes only the documented image/geometry/malformed-annotation/text errors; unknown labels and empty KIE annotation sets alone remain. Read `source_statistics` and `output_statistics` to distinguish input findings from retained records. Split/quarantine counts in the split summary refer to the output, and filtering does not rebalance splits. `fail` returns 2 with the requested policy and both subset diagnostics in `validation_failure_report.json`. A rejected run preserves all four previous success artifacts. The separate failure report may describe an earlier attempt.

Structural validation checks KIE label mapping, text states, geometry issues and bbox consistency, while keeping OCR, KIE, recognition and official inventory distinct. A correctly reported invalid polygon with null bbox is structurally valid; structural PASS does not mean annotation correctness. Manifest versions 1.0/1.1 remain supported with the legacy optional fields and blank-text semantics described in [DATA_SCHEMA.md](DATA_SCHEMA.md).

All files are staged and verified before replacement; ordinary write/replacement failures have regression-tested recovery. Four-file publication is not atomic across a process kill or power loss, and persistent rollback I/O failures/concurrent writers are not covered. Use one writer per directory and verify before consuming. Exact SHA-256 grouping/quarantine is unchanged; missing checksums cannot prove image identity, near-duplicate leakage is not resolved, and no parent receipt/KIE relationship is inferred for recognition crops.

## Local-only artifacts

MC-OCR images, processed manifests/crops, OCR model weights, predictions, transcript text, per-image metrics and notebook outputs are private local artifacts and must not be committed or redistributed without confirming dataset terms.
