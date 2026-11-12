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

recognition_manifest.jsonl --> run_ocr.py --psm 7 --> evaluate_ocr.py --mode crop
                                                        |
                                                        +--> metrics.json
                                                        +--> per_crop_metrics.jsonl

manifest.jsonl --> run_ocr.py --engine phocr-vietocr --> PHOCR detector + VietOCR per candidate
                                                         |
                                                         +--> candidate predictions/failures/runtime
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

PSM 6 remains the default. Use `--psm` to compare another Tesseract page segmentation assumption; the selected value is recorded in `runtime.json`.

### Optional hybrid receipt OCR

The selected receipt hybrid is `phocr-vietocr`: PHOCR supplies text polygons and VietOCR recognizes one perspective crop per validated detector candidate. It is optional and does not change the default Tesseract path or the recognition-crop benchmark.

PHOCR `1.0.3` requires NumPy `<2`, while the core project requires NumPy `>=2`; keep this stack isolated and do not add it to the core extras. The following versions are the GPU setup used for the benchmark:

```bash
PHOCR_VENV=/tmp/docucheck-phocr-vietocr-venv
uv venv "$PHOCR_VENV" --python 3.12
uv pip install --python "$PHOCR_VENV/bin/python" \
  --index https://pypi.org/simple \
  numpy==1.26.4 phocr==1.0.3 onnxruntime-gpu==1.31.1 \
  vietocr==0.3.13 requests==2.32.4 setuptools==78.1.0
uv pip install --python "$PHOCR_VENV/bin/python" \
  --torch-backend cu129 \
  --index https://download.pytorch.org/whl/cu129 \
  --index https://pypi.org/simple --upgrade \
  torch==2.13.0 torchvision==0.28.0
uv pip install --python "$PHOCR_VENV/bin/python" \
  --index https://pypi.org/simple numpy==1.26.4 pillow==10.2.0
```

If the ONNX Runtime wheel cannot find CUDA libraries on the host, expose the CUDA library directory from the tested PyTorch environment before the smoke check. Do not install the project with `-e .` in this environment because that would reintroduce the core NumPy constraint.

Verify the isolated imports and CUDA providers:

```bash
PHOCR_VENV=/tmp/docucheck-phocr-vietocr-venv
GPU_LIB_ROOT=/tmp/docucheck-gpu-venv.xwgOpW/lib/python3.12/site-packages
export LD_LIBRARY_PATH="$GPU_LIB_ROOT/nvidia/cu13/lib:$GPU_LIB_ROOT/nvidia/cudnn/lib:$GPU_LIB_ROOT/nvidia/cuda_runtime/lib:$LD_LIBRARY_PATH"
"$PHOCR_VENV/bin/python" -c \
  "import importlib.metadata as m, onnxruntime as ort, torch, vietocr; print(m.version('phocr'), m.version('vietocr'), ort.get_available_providers(), torch.cuda.is_available())"
```

Download the PHOCR detector and VietOCR weights into ignored local output paths:

```bash
"$PHOCR_VENV/bin/python" scripts/download_recognition_models.py --engine phocr-detector
"$PHOCR_VENV/bin/python" scripts/download_recognition_models.py --engine vietocr
```

Run it on the receipt manifest, not `recognition_manifest.jsonl`:

```bash
CUDA_VISIBLE_DEVICES=0 "$PHOCR_VENV/bin/python" scripts/run_ocr.py \
  --engine phocr-vietocr --device cuda:0 \
  --manifest data/processed/manifest.jsonl \
  --split internal_dev \
  --output-dir outputs/ocr/phocr_vietocr_gpu_internal_dev
```

The default model paths are `outputs/ocr/models/vietocr/vgg_transformer.pth` and `outputs/ocr/models/phocr/official_models/ch_PP-OCRv5_server_det.onnx`; override them with `--model-path` and `--phocr-model-path`. The detector adapter invokes PHOCR detection only; PH-OCRv1 recognition is not used. The output contains deterministic `predictions.jsonl`, `failures.jsonl`, and `runtime.json`: prediction rows retain the receipt ID, detector candidate polygon and ID, detector confidence when available, recognized text, recognition confidence, and statuses. Runtime metadata records detector/recognizer versions, model checksums, devices, direct candidate counts, crop latency, and the no-padding preprocessing choice.

Each validated detector candidate is cropped and recognized independently. The selected path applies no crop padding; the rejected 5% padding experiment remains benchmark-only. This path produces text evidence for later layout-aware/KIE stages, not semantic field labels or business-validation results. A nonzero exit means at least one candidate or receipt failed.

The existing `paddle-vietocr` engine remains available as a comparison path. It detects with PaddleOCR and recognizes each unmerged source-image crop with VietOCR:

```bash
uv sync --extra vietocr --extra paddleocr
uv run --extra vietocr python scripts/download_recognition_models.py --engine vietocr
uv run --extra paddleocr python scripts/download_recognition_models.py --engine paddleocr-detector
```

Run it on the receipt manifest, not `recognition_manifest.jsonl`:

```bash
uv run --extra vietocr --extra paddleocr python scripts/run_ocr.py \
  --engine paddle-vietocr \
  --manifest data/processed/manifest.jsonl \
  --split internal_dev \
  --output-dir outputs/ocr/paddle_vietocr
```

The CLI defaults match the documented local model paths: `outputs/ocr/models/vietocr/vgg_transformer.pth` for VietOCR and `outputs/ocr/models/paddleocr/official_models/PP-OCRv6_medium_det` for the PaddleOCR detector. Override them with `--model-path` and `--detector-model-dir` when needed. The hybrid output contains deterministic `predictions.jsonl`, `failures.jsonl`, and `runtime.json`: prediction rows retain the receipt ID, source polygon, candidate ID, detector confidence, recognized text, recognition confidence, and statuses; failures distinguish candidate-stage errors from receipt-stage errors; runtime metadata records both engines, model identities/checksums, preprocessing, split, counts, and latency.

This path only produces text evidence for the later layout-aware/KIE stages. It does not assign field labels, modify either manifest, or provide KIE/business-validation metrics. A nonzero exit means at least one candidate or receipt failed.

The checked-in optional extras intentionally keep the default environment CPU-only. For a local NVIDIA GPU environment, use a separate virtualenv so Paddle's CUDA runtime and PyTorch's CUDA runtime do not overwrite the CPU stack:

```bash
uv venv /tmp/docucheck-gpu-venv --python 3.12
uv pip install --python /tmp/docucheck-gpu-venv/bin/python -e .
uv pip install --python /tmp/docucheck-gpu-venv/bin/python \
  --index https://pypi.org/simple paddleocr==3.7.0 vietocr==0.3.13 setuptools==78.1.0
uv pip install --python /tmp/docucheck-gpu-venv/bin/python \
  --index https://www.paddlepaddle.org.cn/packages/stable/cu129/ \
  --index https://pypi.org/simple paddlepaddle-gpu==3.3.1
uv pip install --python /tmp/docucheck-gpu-venv/bin/python \
  --torch-backend cu129 \
  --index https://download.pytorch.org/whl/cu129 \
  --index https://pypi.org/simple --upgrade \
  torch==2.13.0 torchvision==0.28.0
```

Verify both runtimes before inference, then pass `--device cuda:0`:

```bash
/tmp/docucheck-gpu-venv/bin/python -c \
  "import torch, paddle; print(torch.cuda.is_available(), paddle.device.is_compiled_with_cuda())"
CUDA_VISIBLE_DEVICES=0 /tmp/docucheck-gpu-venv/bin/python scripts/run_ocr.py \
  --engine paddle-vietocr --device cuda:0 \
  --split internal_dev --output-dir outputs/ocr/paddle_vietocr_gpu_internal_dev
```

The Paddle detector records `gpu:0` and VietOCR records `cuda:0` in `runtime.json`. The CUDA environment tested locally used an RTX 4060 with driver 595.99.02; choose matching wheels for another host.

On Windows, `--tesseract "C:\Program Files\Tesseract-OCR\tesseract.exe"` selects
an executable outside PATH. The controlled PSM comparison and a discovered
full-page transcript parsing defect are documented in
[PSM_COMPARISON_REPORT.md](PSM_COMPARISON_REPORT.md). Historical full-page CER/WER
used incorrectly parsed GT. The corrected comparison uses a separate manifest;
the original `data/processed/manifest.jsonl` is intentionally preserved. Use the
corrected manifest explicitly for full-page evaluation, as documented in the report.

## 5. Evaluate OCR recognition

Evaluation pairs full-page OCR transcript regions (`ocr_regions` in the receipt manifest) with the corresponding image predictions. It does not score KIE field extraction.

```bash
uv run python scripts/evaluate_ocr.py \
  --split internal_dev \
  --output-dir outputs/ocr/evaluation
```

The default prediction path is `outputs/ocr/tesseract_internal_dev/predictions.jsonl`, matching the full run above. The evaluation writes `metrics.json`, `per_image_metrics.jsonl`, and `per_region_alignment.jsonl`. A three-image smoke run is not a substitute for the full split. See [Goal 3 OCR baseline](GOAL3_OCR_BASELINE.md) for alignment rules and metric limits.

## 6. Evaluate the recognition crops directly

The separate recognition manifest contains 5,285 `official_train` and 1,300 `official_val` crop/transcript pairs. PSM 7 treats each crop as one text line. Run and evaluate the two splits separately:

```bash
uv run python scripts/run_ocr.py \
  --manifest data/processed/recognition_manifest.jsonl \
  --split official_val --psm 7 \
  --output-dir outputs/ocr/crop_psm7_official_val

uv run python scripts/evaluate_ocr.py \
  --mode crop \
  --manifest data/processed/recognition_manifest.jsonl \
  --predictions outputs/ocr/crop_psm7_official_val/predictions.jsonl \
  --split official_val \
  --output-dir outputs/ocr/crop_psm7_official_val
```

Repeat with `official_train` in a separate directory. The validation result is the benchmark; the train result is diagnostic and must not be combined with it as one headline score. Crop mode writes `metrics.json` and `per_crop_metrics.jsonl`. It joins Tesseract's emitted words and compares them directly with `text_raw`; prediction polygons do not participate in the score.

### Audit, benchmark, verify, and review

For the complete recognition benchmark workflow, the runner audits every crop, saves a
train layout gallery, locks PSM 7/model/source hashes, and runs train then validation:

```powershell
.\.venv\Scripts\python.exe scripts/run_recognition_benchmark.py --tesseract 'C:\Program Files\Tesseract-OCR\tesseract.exe' --output-dir outputs/ocr/week2/goal1
.\.venv\Scripts\python.exe scripts/verify_recognition_benchmark.py --run-dir outputs/ocr/week2/goal1
.\.venv\Scripts\python.exe scripts/review_recognition_errors.py --metrics outputs/ocr/week2/goal1/official_train/per_crop_metrics.jsonl --output-dir outputs/ocr/week2/goal1/error_review
```

Omit `--tesseract` when it is on PATH. Use `--audit-only` to inspect the train
layout gallery before inference. Choose a fresh run directory for every benchmark
and a fresh review directory for every review; existing locked runs/reviews are
preserved. Metrics include CER/WER, normalized exact match, exclusions and coverage.
The verifier recomputes all scores from saved predictions without repeating OCR.
Open the local `error_review/index.html`, inspect each crop and fill review notes;
selection groups alone do not constitute a completed review. See the
[recognition protocol](WEEK2_RECOGNITION_PROTOCOL.md) for split and failure policies.

The verifier checks the source hashes recorded for that run. After changing the
OCR implementation, use the run's matching source revision or saved source snapshot
to verify historical evidence; a source-hash mismatch does not by itself mean the
saved predictions are corrupt. Keep the original run hashes and artifacts.

## 7. Optional: compare Tesseract, VietOCR, and PaddleOCR

The default Tesseract commands above require no heavyweight Python OCR runtime. Install both optional CPU stacks only when running the three-engine comparison:

```bash
uv sync --extra vietocr --extra paddleocr
uv run --extra vietocr python scripts/download_recognition_models.py --engine vietocr
uv run --extra paddleocr python scripts/download_recognition_models.py --engine paddleocr
```

The model setup stores checkpoints under ignored `outputs/ocr/models/`. Run the recognition engines sequentially to avoid CPU oversubscription, then evaluate each result in the same directory as its `runtime.json`:

```bash
uv run --extra vietocr python scripts/run_ocr.py \
  --engine vietocr \
  --manifest data/processed/recognition_manifest.jsonl \
  --split official_val \
  --output-dir outputs/ocr/vietocr_official_val

uv run python scripts/evaluate_ocr.py \
  --mode crop \
  --manifest data/processed/recognition_manifest.jsonl \
  --predictions outputs/ocr/vietocr_official_val/predictions.jsonl \
  --split official_val \
  --output-dir outputs/ocr/vietocr_official_val

uv run --extra paddleocr python scripts/run_ocr.py \
  --engine paddleocr \
  --manifest data/processed/recognition_manifest.jsonl \
  --split official_val \
  --output-dir outputs/ocr/paddleocr_official_val

uv run python scripts/evaluate_ocr.py \
  --mode crop \
  --manifest data/processed/recognition_manifest.jsonl \
  --predictions outputs/ocr/paddleocr_official_val/predictions.jsonl \
  --split official_val \
  --output-dir outputs/ocr/paddleocr_official_val

uv run python scripts/compare_ocr_engines.py \
  --tesseract outputs/ocr/crop_psm7_official_val \
  --vietocr outputs/ocr/vietocr_official_val \
  --paddleocr outputs/ocr/paddleocr_official_val \
  --output-dir outputs/ocr/engine_comparison
```

The comparison writes `comparison.json` and `per_crop_comparison.jsonl`. It rejects failed or mismatched runs instead of ranking different crop sets. On the recorded 1,300-crop `official_val` comparison run, VietOCR reached CER 0.0959 / WER 0.3387, PaddleOCR CER 0.1744 / WER 0.6303, and Tesseract 5.3.4 PSM 7 CER 0.1951 / WER 0.5549. All three used 23,739 reference characters and 4,815 reference whitespace tokens with zero inference failures.

That comparison uses a different Tesseract run from the 5.5.3.20260724 baseline
in [the recognition benchmark report](WEEK2_REPORT.md), which reports validation
CER 0.2065 / WER 0.5618. Preserve each run's engine version and artifact paths
when citing results. To compare new runs, evaluate the same crop IDs, reference
transcripts and normalization policy, and pass their actual output directories
to `compare_ocr_engines.py`. Choose models and tune parameters on development
data drawn from training; keep official validation for fixed-configuration evaluation.

These are recognition-only results on supplied crops, not full-page detection or KIE scores. The source transcripts may contain annotation noise. Mean latency remains in the artifact for provenance, but model threading and host load were not controlled tightly enough to claim a speed ranking.

## Optional notebooks and code entry points

The notebooks are for local inspection, not required pipeline commands:

- `01_dataset_audit.ipynb` and `02_exploratory_data_analysis.ipynb`: source data inventory and EDA.
- `03_preprocessing_validation.ipynb`: compare source and prepared data and inspect split integrity.
- `04_ocr_baseline_evaluation.ipynb`: inspect OCR metrics and image overlays.

The main code path is `scripts/prepare_dataset.py` → `docucheck.data.preprocessing.prepare_records()`, `scripts/run_ocr.py` → `docucheck.ocr.inference.run_batch()`, and `scripts/evaluate_ocr.py` → `docucheck.evaluation.metrics.evaluate_ocr_records()`.

Do not commit receipt images, transcripts, local manifests, model files, predictions, or review artifacts. Check dataset terms before using or redistributing data.
