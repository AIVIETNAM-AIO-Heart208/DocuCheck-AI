# Dataset and OCR pipeline

Use this guide to follow the implemented data path. The MC-OCR dataset, model, manifests, predictions, and review artifacts stay on the local machine.

```text
MC-OCR source files
        |
        v
prepare_dataset.py -----> manifest.jsonl
        |                  recognition_manifest.jsonl (separate task)
        |                  split_summary.json + validation_report.json
        |
        +---- optional: audit_dataset.py (review pack and duplicate candidates)
        |
        v
run_ocr.py <----- Tesseract + pinned Vietnamese model
        |
        +---------> predictions.jsonl + failures.jsonl + runtime.json
                              |
manifest.jsonl ---------------+----> evaluate_ocr.py
                                      |
                                      +--> metrics.json
                                      +--> per_image_metrics.jsonl
                                      +--> per_region_alignment.jsonl
```

## 1. Prepare manifests

Put MC-OCR under `data/mcocr`, or set `MC_OCR_ROOT`. The raw KIE labels and full-page OCR transcripts become receipt records in `manifest.jsonl`; recognition crop/transcript pairs go into `recognition_manifest.jsonl`.

```bash
uv run python scripts/prepare_dataset.py \
  --dataset-root data/mcocr \
  --output-dir data/processed \
  --seed 42 \
  --validation-fraction 0.2
```

The output directory contains:

- `manifest.jsonl`: receipt images, KIE regions, available full-page OCR transcript regions, and the official validation image inventory.
- `recognition_manifest.jsonl`: a separate crop-recognition task. These crops are not verified as KIE field crops and are not consumed by the receipt OCR baseline.
- `split_summary.json` and `validation_report.json`: split counts, diagnostics, and structural checks for the output bundle.

The default invalid-record policy is `report`, which retains records and reports source issues. `--invalid-policy skip` removes records marked invalid; `fail` rejects invalid output. Verify an existing bundle without rebuilding it with `--verify-only`.

`internal_train` and `internal_dev` are deterministic splits of the receipt training data. Exact image duplicates of official validation images are quarantined. `internal_dev` is the default OCR evaluation split; it is not the official validation set. See [DATA_SCHEMA.md](DATA_SCHEMA.md) for fields and validation semantics.

## 2. Optional: audit data quality

This review step reads `data/processed/manifest.jsonl` and the source images. It creates near-duplicate candidates and an annotation review pack; it does not change splits or confirm candidate pairs automatically.

```bash
uv run python scripts/audit_dataset.py \
  --dataset-root data/mcocr \
  --seed 42 \
  --sample-size 40 \
  --threshold 6 \
  --output-dir outputs/audit/week1
```

Open `outputs/audit/week1/annotations.html` and `near_duplicates.html` locally. The generated `annotation_review.csv` is reviewer work: choose a new output directory if it already exists. See the [annotation review protocol](ANNOTATION_AUDIT.md).

## 3. Download the OCR model

Install Tesseract 5 separately, then download the pinned Vietnamese `vie` model. The script checks its SHA-256 and writes it under ignored local outputs.

```bash
uv run python scripts/download_ocr_model.py
```

## 4. Run the receipt OCR baseline

For a quick smoke run, process three sorted `internal_dev` images:

```bash
uv run python scripts/run_ocr.py \
  --split internal_dev \
  --limit 3 \
  --output-dir outputs/ocr/smoke
```

Run the full internal development split before evaluation:

```bash
uv run python scripts/run_ocr.py \
  --split internal_dev \
  --output-dir outputs/ocr/tesseract_internal_dev
```

This reads `data/processed/manifest.jsonl` and source receipt images, using `outputs/ocr/tessdata_fast` for the model by default. It writes word-level predictions to `predictions.jsonl`, execution failures to `failures.jsonl`, and model/runtime details to `runtime.json`.

## 5. Evaluate OCR recognition

Evaluation pairs full-page OCR transcript regions (`ocr_regions` in the receipt manifest) with the corresponding image predictions. It does not score KIE field extraction.

```bash
uv run python scripts/evaluate_ocr.py \
  --split internal_dev \
  --output-dir outputs/ocr/evaluation
```

The default prediction path is `outputs/ocr/tesseract_internal_dev/predictions.jsonl`, matching the full run above. The evaluation writes `metrics.json`, `per_image_metrics.jsonl`, and `per_region_alignment.jsonl`. A three-image smoke run is not a substitute for the full split. See [Goal 3 OCR baseline](GOAL3_OCR_BASELINE.md) for alignment rules and metric limits.

## Optional notebooks and code entry points

The notebooks are for local inspection, not required pipeline commands:

- `01_dataset_audit.ipynb` and `02_exploratory_data_analysis.ipynb`: source data inventory and EDA.
- `03_preprocessing_validation.ipynb`: compare source and prepared data and inspect split integrity.
- `04_ocr_baseline_evaluation.ipynb`: inspect OCR metrics and image overlays.

The main code path is `scripts/prepare_dataset.py` → `docucheck.data.preprocessing.prepare_records()`, `scripts/run_ocr.py` → `docucheck.ocr.inference.run_batch()`, and `scripts/evaluate_ocr.py` → `docucheck.evaluation.metrics.evaluate_ocr_records()`.

Do not commit receipt images, transcripts, local manifests, model files, predictions, or review artifacts. Check dataset terms before using or redistributing data.
