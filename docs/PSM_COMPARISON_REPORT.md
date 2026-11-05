# Tesseract full-page PSM comparison — 05/11/2026

**Status: Goal 2 complete with documented limitations.** Inference, corrected
evaluation, technical verification and examination of all 20 selected visual cases
are complete. This is not a claim that every cause or annotation has been confirmed
by the user. A full-page transcript parser defect
was found, then corrected with approval. The current results below use real source
transcripts. Original manifests and historical evidence remain unchanged.

Current evidence: `outputs/ocr/week2/goal2_20261105_corrected/`.
Final review revision: `outputs/ocr/week2/goal2_20261105_review_final/`.
The sealed benchmark bundle retains its earlier pending-review state as history;
the separate final review supersedes that status without changing its hashes.
Protocol: [PSM_CORRECTED_PROTOCOL.md](PSM_CORRECTED_PROTOCOL.md).

## Corrected comparison and recommendation

All three runs succeeded on the same 231 images. Text metrics use 4,265 valid
regions with nonempty source transcripts: 56,619 characters and 11,584 whitespace
tokens. Exclusions are 104 invalid-geometry regions and 4,039 empty-transcript
regions, counted disjointly. All 231 images contribute text GT.

| PSM | Micro CER | Micro WER | Character errors | Word errors | Empty pages | Unmatched text GT / 4,265 |
|---:|---:|---:|---:|---:|---:|---:|
| 6 | 0.615712 | 0.819061 | 34,861 | 9,488 | 0 | 902/4,265 (21.15%) |
| 4 | 0.640068 | 0.819406 | 36,240 | 9,492 | 14 | 1,376/4,265 (32.26%) |
| 11 | 0.608365 | 0.815953 | 34,445 | 9,452 | 0 | 837/4,265 (19.62%) |

Two distinct populations are reported; an unassigned word is not necessarily a
false detection when some GT regions lack transcripts:

| PSM | Unassigned to text GT / all boxes | Unassigned to all valid geometry / all boxes | Unmatched geometry / 8,304 |
|---:|---:|---:|---:|
| 6 | 18,459/26,859 (68.73%) | 10,488/26,859 (39.05%) | 1,886/8,304 (22.71%) |
| 4 | 10,915/18,482 (59.06%) | 3,586/18,482 (19.40%) | 2,798/8,304 (33.69%) |
| 11 | 15,490/24,208 (63.99%) | 7,043/24,208 (29.09%) | 1,736/8,304 (20.91%) |

**Conditional recommendation:** PSM 11 is the next candidate for full-page
experiments, with PSM 6 retained as control. It has the lowest observed CER/WER
and unmatched rates, with no empty pages, but does not win reliably on every image.
Keep the production default unchanged pending downstream product checks.
PSM 4 is not recommended as the general default: CER is worse and 14 pages are
empty despite zero execution failures. Its lower unassigned rate alone is not
evidence of better recognition.

PSM 11 improves per-image CER on 110 images, worsens it on 108, and ties on 13.
PSM 4 improves 68, worsens 140, and ties 23. Exploratory paired-image bootstrap
(5,000 resamples, seed 42) gives PSM 11 minus PSM 6 micro CER delta -0.00735,
95% percentile interval [-0.01696, 0.00173]; WER delta -0.00311, interval
[-0.01287, 0.00644]. Both include zero. This is post-run uncertainty analysis,
not a preregistered significance test, and assumes image independence.

These are full-page diagnostics influenced by alignment/reading order and remaining
annotation errors. Blank-transcript regions are not a random sample. Do not equate
these scores with clean crop recognition, detection F1 or product field accuracy.

## Source defect and effect on conclusions

Before correction, `load_full_page_text_records()` in `src/docucheck/data/loader.py` split
each row with `split(",", 10)` and takes field 10 as the transcript. The inspected
source rows instead contain an ID, eight coordinates, transcript (which may
contain commas), and a terminal category. The parser reads a category or a
truncated transcript plus category as ground truth. For example, the suffix
`98,000,TOTAL_COST` becomes `000,TOTAL_COST`; an empty transcript becomes `OTHER`.

All 8,408 source rows on the 231-image development split end in known categories,
and all 8,408 original manifest texts differed from the transcript obtained by
separating the first nine fields and the final category. The source audit found:

| Source property | Regions |
|---|---:|
| Nonempty transcript before geometry filtering | 4,311 |
| Empty transcript before geometry filtering | 4,097 |
| Valid geometry and nonempty transcript | 4,265 |
| Valid geometry and empty transcript | 4,039 |
| Invalid geometry | 104 |

All 231 images have at least one nonempty transcript with valid geometry. Missing
transcripts must not be invented from category names or OCR output. The authorized
correction changes the text-scoring denominator from 8,304 to 4,265 regions;
this is a protocol change, not an OCR accuracy improvement. Geometry-only coverage
over all valid regions must be distinguished from text-evaluation coverage.

This finding concerns full-page sidecars. Goal 1 uses separate recognition
crop/transcript files and a separate parser; its evidence is preserved.

## Completed inference, retained as evidence

Local bundle: `outputs/ocr/week2/goal2_20261105/`. All three runs used the same
231 images, original bytes, Tesseract `v5.5.3.20260724`, pinned `vie.traineddata`
SHA-256 `79df64caf7bcfb2a27df5042ecb6121e196eada34da774956995747636d5bfa1`,
OEM 1, CPU, one worker/batch and `OMP_THREAD_LIMIT=OMP_NUM_THREADS=1`. Runs were
sequential in order 6, 4, 11. Configuration, image hashes, source snapshots and
commands were locked before inference.

| PSM | Successful / attempted | Failures | Empty output images | Word boxes | Total seconds | Mean seconds/image |
|---:|---:|---:|---:|---:|---:|---:|
| 6 | 231/231 | 0 | 0 | 26,859 | 96.513 | 0.4174 |
| 4 | 231/231 | 0 | 14 | 18,482 | 92.512 | 0.4002 |
| 11 | 231/231 | 0 | 0 | 24,208 | 108.723 | 0.4703 |

Runtime is a single observation including subprocess startup, with no repeated
or randomized trials. It does not establish a statistical speed ranking.

### Historical-protocol reproduction, not recognition-quality evidence

The following values are retained to explain the previous evaluation and the
source defect. The CER/WER references are invalid. Spatial counts use the old
8,304-region set, which includes regions whose true source transcript is empty.

| PSM | CER (invalid GT) | WER (invalid GT) | Unassigned words / all words | Unmatched GT / 8,304 |
|---:|---:|---:|---:|---:|
| 6 | 1.872454 | 2.144846 | 10,488/26,859 (39.05%) | 1,886/8,304 (22.71%) |
| 4 | 1.806730 | 2.080964 | 3,586/18,482 (19.40%) | 2,798/8,304 (33.69%) |
| 11 | 1.862727 | 2.217971 | 7,043/24,208 (29.09%) | 1,736/8,304 (20.91%) |

Recorded character error numerators are 92,591 / 89,341 / 92,110, all over
49,449 reference characters; word errors are 18,332 / 17,786 / 18,957 over
8,547 reference tokens, in PSM order 6 / 4 / 11. These denominators include the
misparsed labels. An independent full-matrix edit-distance implementation agrees
with all 24,912 saved region scores, but arithmetic consistency cannot validate GT.

The earlier local PSM 6 bundle also has 10,488/26,859 = 39.05% unassigned.
The documented Tesseract 5.3.4 run has 12,913/29,849 = 43.26%. They are different
runs; do not mix their results. The source of the TA's approximate 39% figure
has not been independently established. Historical full-page CER/WER in
`GOAL3_OCR_BASELINE.md` and `WEEK1_REPORT.md` require the same GT caveat.

## Completed visual review and retained uncertainties

The corrected local HTML gallery contains 20 unique diagnostic cases: candidate CER
improvements/regressions, CER/coverage trade-offs, difficult cases and seed-42
samples, plus successful empty OCR. The gallery under the old run is marked as
superseded; use `goal2_20261105_review_final/index.html` for final observations.
All 20 comparison images were examined and their aligned text/box evidence
cross-checked. Each case includes original image, source-indexed GT,
PSM overlays, confidence/text tables, measurements and a specific review question.

Final observations and limits:

- Case 01: PSM 6 emits only eight boxes and misses much receipt content; PSM 4
  recovers more text, lowering CER from 0.990 to 0.284.
- Case 05: PSM 4 omits the receipt heading section and emits 21 rather than 108
  boxes; CER rises from 0.355 to 0.745. The user explicitly confirms the missing
  heading. No source date was corrected by inference from OCR output.
- Case 07: PSM 11 recovers table/header regions that PSM 6 poorly represents;
  CER drops from 0.657 to 0.303, but word ordering still affects matched lines.
- Case 10: saved aligned text changes from `CASH(VND)-81000` to
  `000 81 - CASH(VND)` for PSM 11. The fixed y-then-x joining rule contributes
  reading-order errors: the four word centers have y values 876.5, 877.0, 878.5,
  879.5 respectively; x order restores `CASH(VND) - 81 000` for this line. This
  verifies an alignment contribution without modifying the locked evaluator.
  The user's feedback remains "chưa chắc", not human confirmation of this finding.
- Case 16: the receipt is sideways; the saved successful PSM 4 prediction is an
  empty list, with no execution failure. The user's "psm4 không xác nhận được"
  is retained. Orientation is an observed condition, not an isolated causal test;
  no definitive claim about GT or the sole cause is made.
- Case 17: the user answers "Không" to the proposed GT-offset hypothesis. This
  disagreement is retained, and the earlier broad statement about GT error is
  withdrawn as an adjudicated conclusion. The trace still shows source polygon
  index 20, reference `370`, y=476..492, receiving PSM 11 token `HĐ:TA981` centered
  at (309,480). This is evidence of the actual assignment, not proof of the sole
  cause. The annotation question remains disputed; no labels or metrics changed.

Other cases cover recovered/missed receipt lines (02–04, 06, 08–09, 12–13),
small text and reading-order errors (11), difficult annotation/alignment cases
(14, 19), sideways receipts with empty or largely incorrect outputs (15, 18),
and a clearer receipt showing a noise/coverage trade-off (20). Every case has
specific observations, two traceable aligned-text examples, a conclusion and a
limitation in the final review JSON/HTML. These deliberately selected cases do
not estimate population error prevalence.

Only case 05 has an explicit user-confirmed observation. Cases 10 and 16 retain
uncertain user feedback; case 17 retains disagreement. The remaining cases were
examined without inventing user sign-off. Completion means the required diagnostic
comparison and error analysis are delivered, not that all annotation causes have
been adjudicated or that the dataset is now clean.

Completed: parser regression tests, a separate evaluation manifest with unchanged
image identities/splits/polygons, re-evaluation of identical predictions, and a new
review selection. The original 231 sidecars agree with all 8,408 corrected
transcripts, including explicit blanks. No image rotation, annotation repair or
new inference was introduced. The recommendation is qualified by these retained
uncertainties. Further annotation repair, image rotation and product validation
are follow-up experiments, not hidden changes to this benchmark.

No production default is changed. PSM 4's 14 empty pages limit its general use.
The next VietOCR pipeline still needs a detector and end-to-end evaluation;
neither these diagnostic text metrics nor lower unassigned-box rates decide that
architecture. No VietOCR implementation is included in this work.

## Reproduction and checks

The corrected run verifies source sidecars, unchanged inference hashes, both
source snapshots, image identities, ID coverage and recomputed aggregate/per-image/
per-region scores. Geometry counts exactly reproduce the old geometry population.
Independent full-matrix edit distances check all 12,795 scored regions across the
three runs. The test suite passes 167 tests, including parser regression cases,
partial-GT coverage, manifest identity preservation, CLI-to-subprocess PSM forwarding
and duplicate/cross-split prediction rejection.

The corrected bundle has 170 passing provenance/coverage/recalculation checks and
216 inventoried artifacts. Its inventory was verified again before final review;
the separate review revision records its own hashes and links to the unchanged
source evidence. Goal 1's 76 evidence files remain unchanged. Final review edits
are documentation/observations only; OCR code, predictions and scores were not
changed during review.

The initial protocol/source snapshot is preserved. The original
`data/processed/manifest.jsonl` intentionally remains unchanged; use the corrected
evaluation manifest explicitly. The comparison runner now rejects the old
misparsed manifest instead of silently benchmarking it. Verify current evidence:

```powershell
.venv\Scripts\python.exe scripts/reevaluate_psm_comparison.py --verify-only --output-dir outputs/ocr/week2/goal2_20261105_corrected
.venv\Scripts\python.exe scripts/verify_psm_evidence.py --run-dir outputs/ocr/week2/goal2_20261105_corrected
```

After source changes, verification requires the matching snapshot; do not rewrite
old source hashes. Predictions, images, model weights and raw transcripts remain
under ignored local outputs. No commit, push or pull request was performed.

To reproduce corrected evaluation into a new directory, use
`scripts/reevaluate_psm_comparison.py --source-run outputs/ocr/week2/goal2_20261105 --output-dir <fresh-directory>`,
then `scripts/review_psm_comparison.py --run-dir <fresh-directory>` and
`scripts/analyze_psm_comparison.py --run-dir <fresh-directory>`. To rerun inference,
pass `--manifest outputs/ocr/week2/goal2_20261105_corrected/manifest.jsonl` and the
explicit Tesseract executable to `scripts/run_psm_comparison.py`, using a new output
directory. Its inference conditions remain PSM 6/4/11, OEM 1 and one thread.
