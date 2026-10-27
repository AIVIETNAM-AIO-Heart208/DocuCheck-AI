# Week 1 Data Schema

All generated manifests and per-image annotations are local-only under `data/processed/`. Paths in the manifest are relative to the configured MC-OCR root; stable image IDs are SHA-256-derived identifiers rather than original filenames.

## Receipt manifest

`manifest.jsonl` contains one record per eligible source receipt:

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

Source KIE labels are retained. Verified mappings are `SELLER` → `seller_name`, `ADDRESS` → `seller_address`, `TIMESTAMP` → `transaction_datetime`, and `TOTAL_COST` → `total_amount`. Unknown labels remain unmapped; the observed `TOTAL_TOTAL_COST` anomaly is not silently corrected. Full-page transcription annotations are a separate source and must not be treated as KIE labels.

Each region carries `text_raw`, `label_raw` (KIE regions), `polygon`, and `validation_issues`. Derived regions may also have `bbox_xyxy` and `canonical_field`. Invalid geometry is retained with issues so audits can account for exclusions instead of losing source records.

## Recognition crop manifest

`recognition_manifest.jsonl` contains normalized field crop records for future recognition experiments. It references the parent `image_id`, field, crop polygon/bounds and local crop path. It is a derived view and does not replace the receipt manifest.

## OCR prediction and evaluation artifacts

`predictions.jsonl` stores one image row with status, latency and Tesseract word-level predictions (`text`, axis-aligned `polygon`, `confidence`). `metrics.json` stores aggregate CER/WER, documented normalization/alignment policy, counts, runtime context and the reason detection F1 is N/A. `per_image_metrics.jsonl` and `per_region_alignment.jsonl` contain private per-image/per-region text and remain ignored under `outputs/`.

CER uses Unicode NFKC, casefolding and whitespace collapse while preserving accents and punctuation. WER uses whitespace-separated Vietnamese syllables; it is not linguistic word segmentation. Recognition alignment assigns a predicted word box to the smallest valid GT polygon containing its center, then sorts words by y and x. GT polygons have coarser line/region granularity than Tesseract word boxes, so one-to-one detection F1 is not meaningful for this annotation pairing.
