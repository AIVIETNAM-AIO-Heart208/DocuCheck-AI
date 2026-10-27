# Week 1 Completion Report

## Goal 1 — Dataset understanding and EDA

The local MC-OCR export contains 1,155 KIE train images and 6,585 annotated field regions. Two rows have empty annotation arrays. Observed source labels are `SELLER`, `ADDRESS`, `TIMESTAMP`, and `TOTAL_COST`, plus one `TOTAL_TOTAL_COST` anomaly retained as unmapped. The official validation inventory contains 391 images but no KIE labels or polygons in this export. Full-page transcription sidecars are available for 1,151 of 1,155 train images, with 40,868 regions; 425 polygons are out of bounds across the full transcription set. Notebooks 01 and 02 provide interactive local galleries, schema/quality audit, resolution and spatial analyses.

## Goal 2 — Reproducible processing

The preparation CLI produces 1,546 receipt records and 6,585 field crop records. Internal split counts are 904 train and 231 development records; 20 exact duplicates of official validation are quarantined. Duplicate-aware splitting leaves no exact duplicate groups crossing internal splits. Repeated preparation runs produced identical manifest hashes. Notebook 03 visually compares source and normalized annotations and checks split integrity.

## Goal 3 — OCR baseline and error analysis

The baseline is Tesseract 5.3.4, CPU, Vietnamese `vie` LSTM model from `tesseract-ocr/tessdata_fast` revision `87416418657359cb625c412a48b6e1d6d41c29bd` (SHA-256 `79df64caf7bcfb2a27df5042ecb6121e196eada34da774995747636d5bfa1`). It uses PSM 6, OEM 1 and TSV word boxes. On `internal_dev`, inference succeeded on 231/231 images and emitted 29,849 parsed word boxes; mean latency was 0.500 seconds per image on the recorded 20-logical-CPU host.

Transcription evaluation used 8,304 valid GT regions from 231 images and excluded 104 regions with invalid geometry. Micro CER was 1.8965 and WER was 2.1795 under the alignment and normalization policy in `DATA_SCHEMA.md`. 1,643 GT regions had no assigned prediction; 12,913 predicted word boxes were outside valid GT polygons. These error rates exceed 1 because insertions are counted and the pairing has substantial coverage/alignment mismatch. They are protocol-specific diagnostic values, not a comparable benchmark score. Detection precision/recall/F1 is N/A because GT region polygons and predicted word boxes have incompatible granularity. Observed failures include missed GT regions, spurious boxes outside annotated text, and GT polygons whose line/group granularity differs from word-level predictions. Notebook 04 shows local overlays and error distributions; it separates OCR quality from the unimplemented KIE task.

A TSV parsing issue was found during evaluation: Tesseract can emit literal tabs/newlines in recognized text, which caused continuation fragments to be interpreted as huge text tokens. The parser now validates the fixed numeric geometry prefix and ignores malformed continuation rows. The full development predictions were regenerated after the fix; maximum parsed text field length was 44 characters.

## Reproduction commands

```bash
uv sync --all-extras
uv run python scripts/prepare_dataset.py --dataset-root data/mcocr --output-dir data/processed --seed 42 --validation-fraction 0.2
uv run python scripts/download_ocr_model.py
uv run python scripts/run_ocr.py --split internal_dev --limit 3 --output-dir outputs/ocr/smoke
uv run python scripts/run_ocr.py --split internal_dev --output-dir outputs/ocr/tesseract_internal_dev
uv run python scripts/evaluate_ocr.py --split internal_dev --output-dir outputs/ocr/evaluation
uv run jupyter lab
uv run pytest
```

Execute notebooks 01 through 04 from the repository root after generating their required manifests and predictions. All data, model files, plots, images, and per-image evaluation artifacts remain local and ignored.

## Phase commits

| Phase | Status | Commit |
|---|---|---|
| 0 | PASS | `c6c68bfc4cb960dbb64a08b3d9e3530c483bfb36` |
| 1 | PASS | `f52c02de328982e19e2b3e403cdbd72dfa433ec1` |
| 2 | PASS | `20641efb3b4394601813887f004d4869dcf048eb` |
| 3 | PASS | `67f0d3df7862a86c18317d72e300edf8f4ecda0a` |
| 4 | PASS | `24e6250f693741ee60210b2e9ada084e12b2dcd0` |
| 5 | PASS | `bca1ad000d0d0ef1f2006c899e45b543145155a8` |
| 6 | PASS | `ef7e2cf4e7979ced7ace53e9989823763c4cbf7d` |
| 7 | PASS | This report and handoff commit (see `git log`) |
