# Week 2 — Goal 1 recognition protocol

Protocol fixed on 2026-11-05 (Asia/Saigon), before this run's inference.
Review-attribution wording was revised after inference on the same date;
numerical evaluation rules are unchanged. The evidence bundle records the revision.

## Inputs and split policy

Use the separate `data/processed/recognition_manifest.jsonl`: 5,285 official
train and 1,300 official validation crops. Audit all images by decoding pixels,
checking original SHA-256 and dimensions, checking unique IDs, transcript/status
validity and cross-split exact duplicates. Stop the run on an audit failure.
Inspect a deterministic train-only gallery (seed 42 plus narrow/short crops) to
check the single-line assumption. This is a sample, not a layout annotation of
all crops. Do not infer a parent receipt or KIE field from a crop.

Use fixed Tesseract `vie`, OEM 1, PSM 7, original crop bytes, CPU, one worker and
batch size one. No resize, thresholding, deskew, fine-tuning or parameter search.
Train is a diagnostic split; validation is evaluated after the configuration is
locked. An internal dev split is unnecessary for this fixed, untuned baseline.
Do not aggregate train and validation scores into one benchmark.

Repository documentation already contains earlier validation PSM 6/7 scores.
This run verifies a fixed baseline on the official validation set; it does not
claim that this set has never been inspected. Any future model selection must
use training-derived development data and preserve the official boundary.

## Recognition metrics and edge cases

Join emitted nonempty Tesseract TSV words in emission order with one space.
Compare directly to the crop transcript; no polygons, detection or alignment.
Normalize both strings with Unicode NFKC, casefold and whitespace collapse;
preserve Vietnamese accents and punctuation.

- Micro CER = sum of character Levenshtein distances / total normalized GT characters.
- Micro WER = sum of token Levenshtein distances / total GT whitespace tokens.
  Vietnamese tokens are usually syllables, not linguistic words.
- Exact match = number of crops with equal normalized strings / evaluated crops.
- CER/WER can exceed one because insertions count.
- Successful inference with no words is an empty hypothesis: score all reference
  characters/tokens as deletions, count it explicitly, exact match is false.
- Missing/failed/malformed inference for any eligible crop aborts evaluation.
  Save failures separately; do not turn execution failures into empty recognition.
- Invalid image, missing/invalid transcript, normalized empty transcript, or
  invalid text status excludes the crop, with disjoint counts in this priority
  order. The benchmark runner's audit requires zero such cases for this dataset.
- Duplicate/invalid manifest IDs (including across splits), duplicate prediction
  IDs and predictions for unknown split IDs fail evaluation.
- Report both eligible prediction coverage and evaluated/all-manifest coverage.

## Evidence and review

`scripts/run_recognition_benchmark.py` audits, freezes configuration/source/model
hashes, runs train then validation, and writes predictions, failures, runtime,
per-crop metrics and aggregate metrics. It refuses a previously locked output
directory. Inference latency includes process startup, image validation and TSV
parsing; it is not neural-network-only latency. Capture package versions,
platform, thread settings, model checksum and evaluation input checksums.

Review at least 20 error crops visually, linking original image, GT, prediction,
CER/WER and specific notes. Include accents, confusable characters, numbers,
small/blurred/skewed text, spacing and empty predictions when observed. Automated
error tags only select examples; pixel inspection determines model error,
source-label/crop problems, mixed causes or uncertainty. Keep source GT unchanged.
The selected examples are a purposive case study, not an estimate of prevalence.
Record reviewer identity only when confirmed. Keep provisional observations
separate from confirmed annotation decisions.

Predictions, transcripts and galleries remain in ignored local `outputs/`.
Commit-ready documentation contains aggregate figures and limitations only.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_recognition_evaluation.py tests/test_ocr_metrics.py tests/test_ocr_baseline.py tests/test_ocr_cli.py -q
.\.venv\Scripts\python.exe scripts/run_recognition_benchmark.py --tesseract 'C:\Program Files\Tesseract-OCR\tesseract.exe' --output-dir outputs/ocr/week2/goal1
```

Use another fresh output directory for a repeat. `--audit-only` stops after the
audit and train layout gallery, before locking/running inference.
