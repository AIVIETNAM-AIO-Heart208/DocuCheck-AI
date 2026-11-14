"""User-run comparison or advisory-guard replay; never loads OCR/models."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from docucheck.extraction.refined import advisory


def read_rows(directory):
    return {r["image_id"]: r for r in map(json.loads, (directory / "extractions.jsonl").read_text(encoding="utf-8").splitlines())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--reference", type=Path, help="Frozen JSON: image_id -> field -> expected value")
    parser.add_argument("--replay-guard", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a new output file")
    if args.replay_guard == bool(args.after):
        raise ValueError("Choose either --replay-guard or --after")
    before = read_rows(args.before)
    report = {"kind": "guard_replay" if args.replay_guard else "comparison",
              "model_executed": False, "rows": [], "missing_or_failed": [],
              "accuracy_verified": False}
    reference = json.loads(args.reference.read_text(encoding="utf-8")) if args.reference else {}
    if args.replay_guard:
        for key, row in before.items():
            if "raw_model_selection" not in row:
                report["missing_or_failed"].append(key)
                continue
            groups = json.loads((args.before / "candidates" / f"{key}.json").read_text(encoding="utf-8"))
            report["rows"].append({"image_id":key, "original_decision":row.get("total_amount_decision"),
                                  "advisory_decision":advisory(row["raw_model_selection"],groups),
                                  "note":"Same registry/IDs. No assessment of new layout selection."})
    else:
        after = read_rows(args.after)
        provenances = [json.loads((p / "provenance.json").read_text(encoding="utf-8")) for p in (args.before,args.after)]
        report["same_ocr"] = provenances[0]["ocr_sha256"] == provenances[1]["ocr_sha256"]
        if not report["same_ocr"]:
            raise ValueError("Different OCR: compare extraction only on identical OCR")
        report["provenances"] = provenances
        for key in sorted(set(before) | set(after)):
            a,b = before.get(key),after.get(key)
            if not a or not b or a.get("status") != "ok" or b.get("status") != "ok":
                report["missing_or_failed"].append(key)
                continue
            for field in ("seller_name","seller_address","transaction_datetime","total_amount"):
                x,y = a["fields"][field]["value_normalized"],b["fields"][field]["value_normalized"]
                item = {"image_id":key,"field":field,"before":x,"after":y,"changed":x!=y,
                        "raw_before":a.get("raw_fields",{}).get(field,{}).get("value_normalized"),
                        "raw_after":b.get("raw_fields",{}).get(field,{}).get("value_normalized")}
                if field in reference.get(key,{}):
                    expected = reference[key][field]
                    item.update(expected=expected,before_correct=x==expected,after_correct=y==expected,
                                regression=x==expected and y!=expected)
                report["rows"].append(item)
        report["scored_fields"] = sum("expected" in r for r in report["rows"])
        report["metrics"] = {}
        for field in ("seller_name","seller_address","transaction_datetime","total_amount"):
            rows = [r for r in report["rows"] if r.get("field") == field]
            scored = [r for r in rows if "expected" in r]
            report["metrics"][field] = {
                "paired_receipts":len(rows), "scored":len(scored),
                "before_correct":sum(r["before_correct"] for r in scored),
                "after_correct":sum(r["after_correct"] for r in scored),
                "regressions":sum(r["regression"] for r in scored),
                "before_non_null":sum(r["before"] is not None for r in rows),
                "after_non_null":sum(r["after"] is not None for r in rows),
                "raw_correct_final_wrong_before":sum(r["raw_before"] == r["expected"] and not r["before_correct"] for r in scored),
                "raw_correct_final_wrong_after":sum(r["raw_after"] == r["expected"] and not r["after_correct"] for r in scored),
                "failed_or_unpaired_receipts":len(report["missing_or_failed"]),
            }
        report["reference_policy"] = "Exact frozen values; image/annotation adjudication remains manual"
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
