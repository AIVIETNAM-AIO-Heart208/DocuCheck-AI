# Week 1 Data Schema

All generated manifests and per-image annotations are local-only under `data/processed/`. Paths are relative to the configured MC-OCR root. `image_id` is a 24-character SHA-256 prefix derived from source subset and relative path, **not** an image-content hash or proof of anonymization. `checksum_sha256` / `image_group_id` hold the full file-content SHA-256. Filenames, paths and raw annotations remain private.

New preparation writes schema `1.1` for all receipt and recognition rows. It adds source diagnostics and explicit empty-text states; existing unique source IDs and split assignments are preserved. Repeated source paths receive a source-line suffix in the ID input, retaining every annotation row. Such IDs depend on source row order. JSONL is UTF-8, one sorted-key JSON object per line, with LF newlines and no machine-specific absolute paths.

Nonfinite numeric values in malformed source geometry serialize as strings (`inf`, `-inf`, `nan`), never non-standard JSON numeric literals. Original source strings and `non_finite_coordinates` diagnostics remain available; these values are not usable geometry.

## Receipt manifest

`manifest.jsonl` contains KIE CSV rows, training images without CSV rows, and official validation inventory images. Default `report` retains invalid rows. Repeated KIE source IDs remain separate records with the same image-content group:

| Field | Meaning |
|---|---|
| `image_id` | Stable anonymized image identifier |
| `image_path` | Relative path to the source image |
| `source_split` | Source division (`train` or validation inventory) |
| `split` | Internal split, official validation inventory, or duplicate quarantine |
| `image_width`, `image_height` | Decoded image dimensions when available |
| `image_status`, `annotation_status` | Explicit availability/validation states |
| `regions` | Source KIE annotations with raw label, mapped field, source text and polygon |
| `ocr_regions` | Full-page transcription regions where sidecar annotations exist |
| `ocr_ground_truth_status` | `available` or a reason ground truth is unavailable |
| `source_annotations`, `source_line` | Original KIE array strings and metadata; logical CSV row number (header = 1) |
| `source_region_counts`, `polygon_parse_error` | Original array lengths and parse failure category |
| `annotation_issues` | Array mismatch, parse failure, repeated source ID, missing labels/text, or unmapped labels |
| `validation_issues` | Geometry findings aggregated from KIE and OCR regions |

Source KIE labels are retained. Verified mappings are `SELLER` → `seller_name`, `ADDRESS` → `seller_address`, `TIMESTAMP` → `transaction_datetime`, and `TOTAL_COST` → `total_amount`. Unknown labels remain unmapped; the observed `TOTAL_TOTAL_COST` anomaly is not silently corrected. Full-page transcription annotations are a separate source and must not be treated as KIE labels.

Each region carries `text_raw`, `label_raw` (KIE regions), `polygon`, and geometry-only `validation_issues`. Derived regions may also have `bbox_xyxy` and `canonical_field`. Invalid geometry is retained with issues and a null derived bbox. Geometry checks cover malformed/nonfinite points, zero area, repeated vertices, self-intersection and image bounds. Unknown dimensions are reported separately. Geometry validity does not establish correct labels, text, or visual alignment.

KIE raw objects remain in `source_geometry`; full-page OCR rows retain `source_raw`, `source_line`, and `source_issue`. OCR provenance is `kie_data/kie_data/boxes_and_transcripts/<source image stem>.tsv`, joined by the explicit matching filename. No OCR region is assigned a KIE label from this join.

Availability states:

- `annotation_status`: `annotated`, `no_kie_row`, `source_annotation_arrays_empty`, or `no_kie_ground_truth_columns_observed`. Detailed annotation problems are orthogonal in `annotation_issues`.
- `text_status`: `present` (nonblank), `empty_in_source` (blank/whitespace), or `missing_in_source` (null). The existing KIE parser treats an entirely empty source cell as an empty array; the original string is retained for disambiguation.
- `label_status`: `mapped`, `unmapped`, `missing_in_source`, or `not_applicable` (OCR).
- `ocr_ground_truth_status`: `unavailable_sidecar`, `empty_sidecar`, `no_usable_transcriptions`, `partial_transcriptions`, `available`, or `unavailable` (official inventory). `available` describes transcription presence; geometry must still be checked separately.
- `image_status`: `valid`, `missing_file`, or an image read/decode error category. Images are fully decoded during inspection.

`validate_manifest().valid` means structural metadata and exact-duplicate checks passed; it does **not** certify source annotation quality. The validator checks nonempty unique IDs, relative paths, schema, split/source-subset agreement, content-group/checksum agreement, valid-image dimensions, text statuses, KIE mapping/statuses and annotation-source separation. It reruns `validate_polygon()`, compares each region's geometry findings and derived bbox, and checks the receipt's aggregate geometry findings. Invalid source geometry with accurate issues and a null bbox is structurally valid. Unknown labels with a null canonical field are also valid; validation never rewrites source labels, transcripts or polygons. OCR regions cannot acquire KIE labels; recognition records cannot carry region metadata; official inventory cannot carry KIE/OCR regions and does not need KIE ground truth.

Supported manifest versions remain `1.0` and `1.1`. For 1.0, legacy `present` means non-null, including blank strings; the previously supported explicit `empty_in_source` state is also accepted. Legacy regions may omit `label_status`, recognition rows may omit `annotation_source`, and versioned official inventory rows may omit the geometry summary. Present fields are still checked. Version 1.1 requires the current label/source diagnostics and distinguishes nonblank, blank and null text. Unversioned inventory rows are not implicitly upgraded.

Invalid-data policies apply to source quality independently of structural validation:

- `report` retains all source records, including geometry/parse errors and unknown labels, with their source annotations and diagnostics.
- `skip` removes receipt records with unreadable/missing images, geometry findings, array mismatches, polygon/OCR parse failures, repeated source IDs, missing labels or missing/empty transcriptions. Empty/missing KIE annotation sets and unknown labels alone are informational and do not remove a record. Recognition records are removed for unavailable crops, missing/empty text or repeated source references. Splitting/quarantine happens before filtering; retained records keep their original assignments, without rebalancing.
- `fail` rejects any of the same quality errors, returns CLI exit code 2, and collects both receipt and recognition diagnostics before stopping. The CLI uses `report` internally for collection but records the requested `invalid_policy: fail`. The direct `prepare_records(..., invalid_policy="fail")` API raises `ValueError` at the first failing subset and writes no files.

`invalid_record_count` and `invalid_recognition_record_count` count source records once each, even if they have multiple errors. Skipped counts describe records removed. `source_statistics` and `output_statistics` use identical counting scopes before and after filtering, including official inventory, region totals, image/text statuses, duplicates and quarantine. Top-level split, duplicate and quarantine counts describe the output; existing top-level image/annotation/geometry/text-quality diagnostics describe the source (receipt image/annotation diagnostics cover the training inventory). Use the nested statistics when comparing source and output. Official inventory is retained by `report`; an unavailable image may be removed/rejected by `skip`/`fail`, without inferring KIE labels. Unsafe/empty source identifiers abort preparation with the source line; raw files remain untouched. An unexpected validation CSV containing KIE columns also aborts rather than discarding new ground truth.

## Recognition crop manifest

`recognition_manifest.jsonl` normalizes the **separate text-recognition crop/transcript task** from `text_recognition_train_data.txt` and `text_recognition_val_data.txt`. It is not generated from KIE polygons. The export provides no verified parent-receipt or KIE-field relationship, so there are no inferred parent IDs, field labels or crop polygons. Equal record counts across datasets do not establish such a relationship.

| Field | Meaning |
|---|---|
| `schema_version`, `image_id`, `image_path` | Schema and crop identity; path relative to dataset root |
| `source_subset`, `source_split` | `text_recognition`; source `train` or `val` |
| `annotation_source`, `source_line`, `source_image_ref` | Source manifest filename, 1-based line and verbatim image reference |
| `split`, `split_provenance` | `official_train`, `official_val`, or `excluded_duplicate_of_official_val` |
| `checksum_sha256`, `image_group_id` | Exact crop file hash; null if unreadable |
| `image_width`, `image_height`, `image_status` | Crop image availability and decoded dimensions |
| `text_raw`, `text_status`, `annotation_issues` | Verbatim transcript, availability, repeated-reference diagnostics |

Use these pairs for crop recognition only. No KIE field-crop manifest is currently produced. Receipt and recognition split policies are independent; preparation checks exact leakage across their combined output as well.

## Split policy and optional audits

Receipt SHA-256 groups are sorted then shuffled with `random.Random(seed)`. Dev group count is rounded from the configured fraction and bounded to leave at least one train group; a single group remains train. This is a **group fraction**, not a guaranteed image fraction. Missing hashes use the same fallback key for grouping and assignment. Matching official validation hashes are quarantined before internal splitting; quarantine rows are intentionally excluded from active-split leakage checks.

`scripts/audit_dataset.py` performs a separate, optional 63-bit DCT pHash audit (default Hamming threshold 6). It compares internal train/dev and each internal split against official validation, omitting quarantined rows. Exact matches are counted separately. Candidate IDs, paths, distances, failures and local galleries stay under ignored `outputs/`; no automatic merge, deletion or split reassignment occurs. This heuristic can confuse common layouts and miss substantial rotations/crops. See [annotation audit protocol](ANNOTATION_AUDIT.md) for human review and missingness interpretation.

## Reproducibility and output safety

Given identical input bytes, source row order, seed, fraction and code/environment, preparation writes identical bytes for `manifest.jsonl`, `recognition_manifest.jsonl`, `validation_report.json` and `split_summary.json`. JSON is strict UTF-8, with sorted keys and LF newlines; output paths and timestamps are not embedded. Reordering repeated source rows can change their line-derived IDs. Neither schema version nor the splitting algorithm is changed by these checks.

The CLI serializes all four files into a temporary directory under the output directory, then validates the serialized bundle before publishing. It backs up existing artifacts and restores already replaced files if a normal replacement raises `OSError`; the validation report is replaced last. Serialization failures leave the prior bundle untouched. Policy or structural rejection writes only `validation_failure_report.json`, leaving all four previous success artifacts intact. This failure report is separate, can remain after later successful runs, and is not the current bundle's validation report. Errors that prevent collecting diagnostics (for example a missing input manifest) are printed to stderr and return 2.

The success report's `artifact_sha256` covers the two JSONL files and split summary. Verify an existing bundle without reading source images:

```bash
uv run python scripts/prepare_dataset.py --output-dir outputs/audit/my_preparation --verify-only
```

Verification checks file hashes, strict JSON, structural/leakage validation, split summary, record counts and output statistics. Missing, changed or mixed artifacts return 2. Older bundles without checksums need regeneration into a separate directory before using this verification command. The report cannot contain its own hash; hashes and consistency checks detect accidental mixing/corruption, not malicious modification.

Publication is not an atomic four-file filesystem transaction. Process termination, power loss, a persistent I/O failure during rollback, or concurrent writers are outside the tested rollback guarantee. Use one writer per output directory, verify before consuming artifacts, and regenerate into a new directory if verification fails. Staging and backups require additional local disk space. Synthetic tests inject serialization and replacement errors at all four publication steps, including a failed first publication. Raw images/annotations are never changed, and no near-duplicate policy is applied here.

## OCR prediction and evaluation artifacts

`predictions.jsonl` stores one image row with status, latency and Tesseract word-level predictions (`text`, axis-aligned `polygon`, `confidence`). `metrics.json` stores aggregate CER/WER, documented normalization/alignment policy, counts, runtime context and the reason detection F1 is N/A. `per_image_metrics.jsonl` and `per_region_alignment.jsonl` contain private per-image/per-region text and remain ignored under `outputs/`.

CER uses Unicode NFKC, casefolding and whitespace collapse while preserving accents and punctuation. WER uses whitespace-separated Vietnamese syllables; it is not linguistic word segmentation. Recognition alignment assigns a predicted word box to the smallest valid GT polygon containing its center, then sorts words by y and x. GT polygons have coarser line/region granularity than Tesseract word boxes, so one-to-one detection F1 is not meaningful for this annotation pairing.
