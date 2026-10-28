# Reproducible local annotation review

Generate manifests first, then run from the repository root:

```bash
uv run python scripts/audit_dataset.py --dataset-root data/mcocr --seed 42 --sample-size 40 --threshold 6 --output-dir outputs/audit/week1
```

Use `--mode annotations` or `--mode near-duplicates` for either audit alone. Use a fresh output directory for another annotation run: the CLI refuses to overwrite an existing review CSV. Outputs contain private receipts and paths and must stay local. No human review has been performed by this command.

## Sampling and visual evidence

`select_annotation_audit_sample()` in `eda.py` selects up to 40 distinct source-train receipts with seed 42. It visits overlapping strata in increasing population order, shuffles candidates deterministically, then samples round-robin without replacement. Strata include KIE/OCR geometry anomalies, unmapped labels, empty KIE arrays, unavailable/incomplete OCR GT, lower/upper sharpness quartiles, field-coverage patterns and low/high KIE region counts (boundary: four regions). Quarantined source-train receipts may be sampled; official validation is excluded from the annotation review.

This is a diagnostic sample enriched for edge cases, not an unbiased estimate of dataset annotation error rates. Sharpness is Laplacian variance, an image-detail heuristic; neither its quartiles nor brightness/contrast are ground-truth quality classes. The existing notebooks already cover resolution, aspect ratio, field frequency/coverage, spatial distributions, density and image-quality heuristics. No additional chart is needed to duplicate those analyses.

Open `annotations.html`: each selected image shows original KIE polygons, region indices, raw labels, canonical fields and automated metadata. `annotation_sample.jsonl` records selection reasons and metadata. Inspect the original source and OCR sidecar separately when a reason concerns OCR geometry rather than KIE polygons. The existing `plot_standardized_record(..., region_key="ocr_regions")` helper supports that view locally.

## Reviewer worksheet

Fill `annotation_review.csv`; every row initially has `review_status=not_reviewed`, with all judgment columns blank. Automated counts never populate these judgments.

1. Set `review_status` to `reviewed` only after inspecting source image and annotations. Set `annotation_correctness` to `correct`, `incorrect`, or `uncertain`.
2. Record `yes`, `no`, or `uncertain` for `wrong_label`, `wrong_geometry`, `missing_field_annotation`, `unreadable_text`, and `uncertain`. Valid geometry alone cannot justify `correct`.
3. Identify affected `region_indices` (zero-based overlay numbers) and `field`. In `evidence_notes`, describe visible evidence, source disagreement and any uncertainty. Avoid copying receipt text unless necessary; keep all notes local.
4. A field with no labeled region is **not annotated**, not proven absent. Confirm absence only when the reviewer has inspected the relevant readable content and records that evidence. If the source or image cannot establish it, mark uncertain.
5. Add `reviewer` and `reviewed_at`. A second reviewer should adjudicate uncertain/disputed cases before conclusions are reported. Preserve original annotations; corrections belong in a separately versioned adjudication artifact.

Report completed/reviewable/sample counts, issue counts and uncertainty explicitly. Do not extrapolate this stratified sample's proportions to the entire dataset. Until this worksheet is completed, human annotation correctness is **NOT VERIFIED**.

## Missingness interpretation

`summarize_field_missingness()` reports `with_label`, `without_label_annotation` and `ground_truth_unavailable`; these three partition the selected records. `with_invalid_geometry` and `with_missing_or_empty_text` overlap the labeled records and each other. Unknown labels are counted separately and never forced into a known field. `confirmed_field_absent=null` means no absence evidence was supplied, not zero absent fields.

## Near-duplicate review

Open `near_duplicates.html` and inspect candidates in `near_duplicate_candidates.jsonl`. Compare transaction-specific content locally, not just the merchant layout. Record confirmed duplicate / different transaction / uncertain in a separate local review file, citing both opaque IDs. No candidates are automatically confirmed, removed or moved between splits. A future split-policy change needs reviewed evidence and a versioned regeneration; this audit leaves the historical split intact.

`near_duplicate_summary.json` records the method, threshold, comparison counts, exact matches, candidate counts and unreadable-image count. Failures are in `near_duplicate_failures.jsonl`. The pHash utility checks resize/compression similarity; it does not guarantee robustness to rotation, cropping, perspective or all small edits. Repeated layouts can produce false positives. Candidates are not proof of leakage, and no candidates would not prove absence of leakage.
