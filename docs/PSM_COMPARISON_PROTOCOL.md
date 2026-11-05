# Full-page PSM comparison protocol

Compare PSM 6 (control), 4 and 11, in that order, on exactly the same 231
`internal_dev` receipt images. This is development-set diagnostic evaluation,
not a new holdout recognition benchmark. The only intended OCR configuration
change is PSM. Use original image bytes, Tesseract Vietnamese `vie`, OEM 1,
one worker, batch size one, and `OMP_THREAD_LIMIT=OMP_NUM_THREADS=1`.
Lock engine, model, manifest, image and source checksums before inference.

Decode every image and verify its manifest checksum and dimensions. Require
unique IDs, full-page GT and exact successful prediction coverage. A successful
empty OCR result is scored as deletions; inference failures prevent comparison.
Exclude GT with geometry validation issues or missing polygons, then missing or
normalized-empty transcripts, and record each exclusion with its source index.
Do not repair annotations or regenerate splits during this experiment.

Keep the existing alignment: assign word centers to the smallest containing
valid GT polygon, order words by center y then x, and join with spaces. Keep NFKC,
casefold and collapsed whitespace; preserve diacritics and punctuation. CER/WER
use summed edit distances divided by summed reference characters/whitespace
tokens. Rates can exceed one. This combines recognition, segmentation, reading
order, annotation and alignment effects; it is not recognition-only accuracy.
Do not derive detection precision/recall/F1 from incompatible region granularity.

Report unassigned words over all emitted words, and unmatched GT over evaluated
GT regions, with numerator and denominator. Report empty pages, failures, total
and mean runtime. Runtime is one sequential observation including process startup,
not a controlled statistical speed benchmark. No minimum accuracy threshold.

Use fresh output directories. Store all image/text artifacts under ignored outputs.
Re-evaluate predictions and compare aggregate, per-image and per-region results.
Verify image/source/model hashes and identical IDs/configuration across runs.
Source snapshots preserve the exact implementation; future source changes must
not be hidden by rewriting historical hashes. Goal 1 evidence remains unchanged
and must be verified with its matching source version.

Select approximately 20 unique images deterministically across improvement,
regression, CER/coverage trade-offs, difficult images and a fixed-seed sample.
Show the same original image with GT and each PSM, plus aligned transcripts and
unassigned word lists. Selection is diagnostic, not a representative prevalence
estimate. Record selection criteria and questions. Leave visual adjudication
pending until the reviewer confirms observations; separate measured effects
from hypotheses. A final PSM recommendation depends on this review and on the
downstream task; no mode is presumed best in advance.

Historical results from Tesseract 5.3.4 and local 5.5.3 are separate runs. Trace
the approximately 39% versus 43.3% unassigned rates to their counts and versions
without assuming the source of the TA's figure.
