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

## Local-only artifacts

MC-OCR images, processed manifests/crops, OCR model weights, predictions, transcript text, per-image metrics and notebook outputs are private local artifacts and must not be committed or redistributed without confirming dataset terms.
