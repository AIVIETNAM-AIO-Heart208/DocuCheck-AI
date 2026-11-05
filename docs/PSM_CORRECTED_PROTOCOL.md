# Full-page PSM comparison: corrected transcript protocol

Revision 2, authorized on 05/11/2026 after source inspection discovered category
labels being used as transcripts. Revision 1 and its inference artifacts remain
unchanged in `outputs/ocr/week2/goal2_20261105/`. This revision supersedes the
text-evaluation assumptions of `PSM_COMPARISON_PROTOCOL.md`.

The sidecar schema is: ID, eight coordinate values, transcript (which may contain
commas), terminal category. Preserve the raw row and category as provenance;
never treat the category as text or infer a missing transcript. Unknown terminal
categories require inspection. Keep the original 231 image IDs, split membership,
image paths/checksums and every polygon. Create a separate 231-row evaluation
manifest; do not replace `data/processed/manifest.jsonl` or regenerate splits.

There are 8,408 regions: 104 have invalid geometry; of the 8,304 remaining regions,
4,265 have nonempty source transcripts and 4,039 have empty source transcripts.
All 231 images have at least one valid nonempty transcript. Explicitly accept
`partial_transcriptions` as partial text GT; do not silently drop these images.
Exclude invalid geometry before counting empty-transcript exclusions.

Report two distinct alignment scopes using the same center-containment rule:

1. **Text scope:** assign OCR word centers to the smallest valid GT polygon with
   a nonempty transcript; sort assigned words by center y then x. CER/WER and
   text unmatched/unassigned metrics refer to these 4,265 regions only.
2. **Geometry scope:** assign centers to the smallest of all 8,304 valid polygons,
   including those without transcripts. Report unmatched regions / 8,304 and
   unassigned words / all emitted words separately. This matches the spatial
   population used by the earlier protocol but is not a detection F1 measure.

The two assignments can differ where polygons overlap; do not mix their counts.
Words outside text GT are not scored as insertions in CER/WER. Untranscribed
regions are not a random sample, so CER/WER describe available annotated text,
not the accuracy of all receipt content or final extracted fields.

Keep NFKC, casefold, collapsed whitespace, Vietnamese diacritics and punctuation;
use micro-averaged character/whitespace-token Levenshtein distances. Successful
empty OCR output is deletions on the nonempty text references. Failed/missing,
duplicate or wrong-split predictions invalidate comparison.

Reuse PSM 6/4/11 predictions from the locked v1 inference only after checking image
identity and all prediction/runtime/failure hashes. OCR itself never consumed
the GT text. No accuracy improvement may be claimed by comparing v1 invalid-GT
CER/WER with v2 corrected-GT CER/WER. Record the old inference source snapshot
separately from the revised evaluation source snapshot.

Create fresh metrics, independent edit-distance verification, artifact inventory,
and a new 20-image review selection. Keep decisions pending for user adjudication.
Record measured changes separately from visual observations and proposed causes.
No automatic annotation correction or production default change follows from
the comparison. Hardware, runtime limits and downstream VietOCR boundaries remain
as in the original protocol.
