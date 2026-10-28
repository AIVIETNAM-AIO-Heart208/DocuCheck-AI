# Week 1 Completion Report

## Goal 1 — Dataset understanding and EDA

The local MC-OCR export contains 1,155 KIE train images and 6,585 annotated field regions. Two rows have empty annotation arrays. Observed source labels are `SELLER`, `ADDRESS`, `TIMESTAMP`, and `TOTAL_COST`, plus one `TOTAL_TOTAL_COST` anomaly retained as unmapped. The official validation inventory contains 391 images but no KIE labels or polygons in this export. Full-page transcription sidecars are available for 1,151 of 1,155 train images, with 40,868 regions; 425 polygons are out of bounds across the full transcription set. Notebooks 01 and 02 provide interactive local galleries, schema/quality audit, resolution and spatial analyses.

## Goal 2 — Reproducible processing

The preparation CLI produces 1,546 receipt records and 6,585 **separate text-recognition crop/transcript records** (5,285 source train and 1,300 source validation). The latter are loaded from the official recognition text files, not cropped from KIE polygons. The fact that KIE also has 6,585 annotated regions does not establish a parent/field relationship. Internal receipt split counts are 904 train and 231 development records; 20 exact duplicates of official validation are quarantined. Duplicate-aware splitting leaves no exact duplicate groups crossing active splits. Repeated preparation runs produced identical manifest hashes. Notebook 03 visually compares source and normalized annotations and checks split integrity.

## Goal 3 — OCR baseline and error analysis

The measurements below are the previously reported baseline, not rerun during the 2026-10-28 Goal 1/2 audit. OCR code, model, predictions and benchmark are unchanged. New geometry findings in that audit concern KIE polygons; the 425 OCR out-of-bounds regions remain unchanged.

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

Exact notebook execution commands used during final validation:

```bash
uv run python -m jupyter nbconvert --to notebook --execute --inplace notebooks/01_dataset_audit.ipynb
uv run python -m jupyter nbconvert --to notebook --execute --inplace notebooks/02_exploratory_data_analysis.ipynb
uv run python -m jupyter nbconvert --to notebook --execute --inplace notebooks/03_preprocessing_validation.ipynb
uv run python -m jupyter nbconvert --to notebook --execute --inplace notebooks/04_ocr_baseline_evaluation.ipynb
```

The original implementation reported `uv run pytest -q` (24 passed), all four original script `--help` commands, Python imports through the test suite, and negative CLI checks for missing input files. It reported execution of all four notebooks, followed by output stripping. These are historical validation claims; the independently executed re-audit below supersedes the Goal 1/2 evidence.

## Re-audit — 2026-10-28

Starting state: branch `main`, commit `2955a891a31fec18ee8a6633855ef984bdb020f3`. Notebooks 01/02 already had local modifications and `Untitled.ipynb` was untracked; those files were preserved. No commit or push was performed. Python 3.12.16 and the existing environment were used; baseline tests independently passed 24/24 (with a pre-existing pytest-cache permission warning). Final tests use an ignored output cache.

### Pre-execution verification

| Finding | Conclusion and evidence | Severity | Action |
|---|---|---|---|
| Recognition manifest described as KIE crops | CONFIRMED: `prepare_records()` calls `load_text_recognition_pairs()`; schema/handoff claimed parent IDs and polygons that did not exist | High | Correct schema, report, handoff and README |
| Confused counts | CONFIRMED semantic error: independent sources each contain 6,585 rows/regions | Medium | Distinguish KIE regions from recognition pairs |
| Missing group-key fallback | CONFIRMED: five records without `image_group_id` raise `KeyError`; with `None`, all five incorrectly become train | High | Reuse the grouping key during assignment; regression tests |
| SHA-only duplicate audit | CONFIRMED: `splitting.py` checks SHA-256 groups; existing quarantine works; no perceptual audit existed | Medium | Add optional candidate-only DCT pHash utility |
| No systematic qualitative audit | PARTIALLY CONFIRMED: notebooks had a four-image sample and feature-extreme galleries, but no stratified worksheet/protocol | Medium | Seeded 40-image pack and human review protocol |
| `SELLER_ADDRESS` label | CONFIRMED in `idea.md`; CSV/config/loader use `ADDRESS` | Low | Correct brief |
| Unclear annotation validation states | PARTIALLY CONFIRMED: missingness/geometry states existed, but empty text, raw parse errors, repeated IDs and path checks were incomplete | High | Preserve provenance, add explicit diagnostics and schema 1.1 |

Additional verified defects: `validate_manifest()` accepted an empty ID and `C:/private/a.jpg`; `validate_polygon()` accepted the nonzero-area crossing polygon `[[0,0],[6,5],[0,4],[4,0]]`. `source_by_name` overwrote repeated KIE CSV IDs. These now have regression coverage. Official inventory rows previously lacked `schema_version`; all generated subsets now declare 1.1.

### Independently recomputed data statistics

The local dataset exists and was read directly. There are 1,155 train images, 391 official validation images, 1,546 receipt manifest rows, and 6,585 recognition pairs. All 8,131 image records decode successfully. No recognition crops are missing; all 6,585 recognition transcripts are nonblank. The validation sample CSV has `img_id`, `anno_image_quality`, `anno_texts`, and **no KIE label/polygon columns**. It cannot establish KIE ground truth.

| KIE label | Regions | Train images with label | Train images without label annotation |
|---|---:|---:|---:|
| SELLER | 1,171 | 1,071 | 84 |
| ADDRESS | 1,952 | 1,077 | 78 |
| TIMESTAMP | 1,347 | 1,088 | 67 |
| TOTAL_COST | 2,114 | 1,081 | 74 |
| TOTAL_TOTAL_COST (unmapped) | 1 | Not mapped to a target field | Not inferred |

Two train rows have empty annotation arrays; array lengths otherwise agree. No-label counts do not prove field absence. For each field, 391 additional official-validation records have unavailable KIE ground truth. No field-absence judgment or human annotation-correctness result is claimed.

Full-page transcription sidecars cover 1,151 train images and contain 40,868 regions; four images lack a sidecar. The strengthened geometry audit finds:

- 425 out-of-bounds OCR regions across 109 images, unchanged from the original report.
- Six invalid KIE regions across six other images with nonadjacent edge intersections/touches, including four with repeated vertices. These affect three SELLER and three ADDRESS regions. They were missed by the old area/bounds-only check.
- 115 receipt records with image/geometry/structural errors in total (all caused by geometry in this export). All are retained under default `report`; derived bboxes for invalid regions are null. Issue categories overlap, so 425 + 4 + 6 is not a count of distinct bad regions.

### Duplicate and annotation audit outputs

Exact source-train duplicate statistics remain 31 groups / 64 records. Twenty groups matching official validation are quarantined. Active splits have zero exact-duplicate leakage, including the combined receipt/recognition manifest check. Receipt IDs and every existing receipt split assignment match the pre-change manifest exactly: **904 train / 231 dev / 20 quarantine / 391 official inventory**.

The optional 63-bit DCT pHash audit, threshold 6, hashed 1,526 nonquarantined receipt images with zero read failures. It compared 208,824 train/dev pairs, 353,464 train/official-validation pairs and 90,321 dev/official-validation pairs. It found **36 candidates**: 10 train/dev, 22 train/official validation, 4 dev/official validation. These are unreviewed similarities, not confirmed duplicate transactions; common layouts can match. No split was changed.

The seeded sample contains 40 distinct source-train images and 40 successfully rendered KIE overlays. Overlapping strata include 10 geometry-anomaly cases, the one unmapped-label case, both empty-annotation rows, all four unavailable-sidecar cases, 13 low-sharpness and 9 high-sharpness heuristic cases, with varying field coverage and annotation density. Every worksheet row is `not_reviewed`. See [ANNOTATION_AUDIT.md](ANNOTATION_AUDIT.md) for the protocol. Automated findings and human judgments remain separate.

Private artifacts: `outputs/audit/week1/{annotations.html,annotation_review.csv,annotation_sample.jsonl,near_duplicates.html,near_duplicate_candidates.jsonl,near_duplicate_summary.json,audit_summary.json}`. Opening or editing these locally does not publish them. The CLI's refusal to overwrite an existing worksheet was tested: exit 2, worksheet SHA-256 unchanged.

### Test and reproducibility evidence

Final suite: **60 passed, 0 failed** with `.venv\Scripts\python.exe -m pytest -q -o cache_dir=outputs/audit/pytest_cache`. New synthetic tests cover missing checksums, duplicate/single groups, invalid fractions, seed/order determinism, quarantine, malformed/empty sidecars, invalid IDs/paths, repeated source rows, corruption/missing images, strict JSON for nonfinite values, recognition provenance, field missingness, stratified selection and resize/JPEG perceptual candidates.

Real-data commands (repository root; `uv run python` is equivalent to the existing venv executable used here):

```bash
python scripts/prepare_dataset.py --dataset-root data/mcocr --output-dir data/processed --seed 42 --validation-fraction 0.2
python scripts/prepare_dataset.py --dataset-root data/mcocr --output-dir outputs/audit/repeat_preparation --seed 42 --validation-fraction 0.2
python scripts/audit_dataset.py --dataset-root data/mcocr --output-dir outputs/audit/week1 --seed 42 --sample-size 40 --threshold 6
```

Both manifests, `validation_report.json`, and `split_summary.json` are byte-identical across repeated preparations. Manifest SHA-256 values:

| File | SHA-256 |
|---|---|
| `manifest.jsonl` | `bfc183cebe9595cba03e54209b18b2f3fddfc5223675ebbacc70b6dd3010d56c` |
| `recognition_manifest.jsonl` | `159f17911783b6465f9b5ffd37de97d4a086722446aac05baf38e3997f8abf87` |

`validate_manifest()` passes all 8,131 records, separately from the 115 source-quality findings. All five script `--help` commands return 0. Seven negative CLI checks (missing dataset/manifest, invalid fraction/threshold/sample size, OCR/evaluation missing manifest) return 2 without tracebacks. No OCR model download or benchmark was run.

Notebooks 01, 02 and 03 execute successfully via `nbclient.NotebookClient`, using the local dataset and generated manifests. Executed copies are under ignored `outputs/audit/notebooks/`; source notebook outputs are not populated. Notebook 03's conclusion was corrected for the new KIE geometry findings. Notebook 04 was not executed in this task because Goal 3 is unchanged. Windows Jupyter emitted event-loop/profile permission warnings during initial execution, but no notebook cell failed.

### Readiness and remaining risks

- **Goal 1: PARTIAL.** Inventory, coverage and automatic validation are verified; the reusable review pack is ready. Human annotation correctness and candidate adjudication are not verified.
- **Goal 2: PASS for the requested engineering work.** Preparation, source preservation, structural validation, deterministic splits and exact-duplicate quarantine have real-data and synthetic-test evidence. This is not a claim that the source annotations are error-free or that all near-duplicate leakage has been ruled out.
- **Goal 3: UNCHANGED.** Existing OCR tests pass, but no new OCR/KIE training, inference or benchmark result is claimed.

Human review must resolve the 36 perceptual candidates and the 40-image sample. pHash is a layout/similarity heuristic with false positives and false negatives, and this implementation performs quadratic pair comparison; it is appropriate for the Week 1 receipt inventory, not arbitrary large corpora. Recognition-task parent receipt links remain unavailable. The source lacks official validation KIE labels and confirmed field-absence annotations. Dataset redistribution terms and the existing OCR alignment limitations remain as previously documented.

## Blockers and Week 2 readiness

Week 2 can import normalized records, split assignments, OCR predictions and reusable metrics directly from the documented Python modules/JSONL files; no notebook execution is required. The main evaluation limitation is the mismatch between word-level predictions and coarser GT regions, which makes CER/WER alignment-sensitive and detection F1 unavailable. KIE training and field extraction remain intentionally unimplemented. MC-OCR redistribution terms were not available in the local project files; no dataset assets are included, and the terms must be confirmed before redistribution.

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
| 7 | PASS | `c04cfa497d4baf4b903650f3c6c2c5e8dd7283b2` |
