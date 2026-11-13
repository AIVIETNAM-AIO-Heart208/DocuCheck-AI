"""Compare frozen expected sidecar with saved runs; never used in inference."""

import argparse
import json
from pathlib import Path


def read(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def review(root):
    expected = json.loads((root / "expected.json").read_text(encoding="utf-8"))
    sources = [Path(p) for p in json.loads((root / "sources.json").read_text())]
    entries = []
    for i, source in enumerate(sources):
        baseline = {r["image_id"]: r for r in read(source / "extractions.jsonl")}
        after = {
            r["image_id"]: r
            for r in read(root / f"batch_{i + 1:02d}/extractions.jsonl")
        }
        for record in read(source / "manifest.jsonl"):
            key = record["image_id"]
            old, new = baseline.get(key, {}), after.get(key, {})
            changed = []
            for field in (
                "seller_name",
                "seller_address",
                "transaction_datetime",
                "total_amount",
            ):
                before = old.get("fields", {}).get(field, {}).get("value_normalized")
                final = new.get("fields", {}).get(field, {}).get("value_normalized")
                raw = new.get("raw_fields", {}).get(field, {}).get("value_normalized")
                truth = expected.get(key, {}).get(field)
                entries.append(
                    {
                        "image_id": key,
                        "field": field,
                        "expected": truth,
                        "before": before,
                        "raw": raw,
                        "after": final,
                        "before_correct": before == truth
                        if truth is not None
                        else None,
                        "after_correct": final == truth if truth is not None else None,
                    }
                )
                if before != final:
                    changed.append(field)
    summary = {}
    for field in ("total_amount", "transaction_datetime"):
        subset = [
            e for e in entries if e["field"] == field and e["expected"] is not None
        ]
        summary[field] = {
            "scorable": len(subset),
            "before_correct": sum(e["before_correct"] for e in subset),
            "after_correct": sum(e["after_correct"] for e in subset),
            "guard_harmed": sum(
                e["raw"] == e["expected"] and e["after"] != e["expected"]
                for e in subset
            ),
        }
    summary["other_changes"] = [
        e
        for e in entries
        if e["field"] in {"seller_name", "seller_address"} and e["before"] != e["after"]
    ]
    (root / "review.json").write_text(
        json.dumps(
            {"summary": summary, "entries": entries}, ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )
    lines = [
        "# Parser/guard review",
        "",
        "Expected frozen in expected.json; money from annotation or visual review, not product parser.",
        "",
        json.dumps(summary, ensure_ascii=False, indent=2),
        "",
        "| Image | Field | Expected | Before | Raw after | Final after |",
        "|---|---|---|---|---|---|",
    ]
    lines.extend(
        "| "
        + " | ".join(
            str(e[k]).replace("\n", " / ").replace("|", "\\|")
            for k in ("image_id", "field", "expected", "before", "raw", "after")
        )
        + " |"
        for e in entries
        if e["field"] in {"total_amount", "transaction_datetime"}
    )
    (root / "review.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    review(parser.parse_args().directory)
