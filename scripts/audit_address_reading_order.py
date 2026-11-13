"""Replay saved selections against before/after address resolvers, without a model.

The run directory must contain sources.json ({source, snapshot} entries) and
baseline/code/candidates.py captured before the change. Artifacts are never
overwritten. This measures layout changes, not fresh model inference accuracy.
"""

import argparse
import html
import importlib.util
import json
import os
import shutil
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from docucheck.extraction.candidates import resolve
from docucheck.extraction.export import export_receipts
from docucheck.extraction.qwen import FIELDS, normalize, render_demo, write_json


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    directory = args.run_dir.resolve()
    spec = importlib.util.spec_from_file_location(
        "docucheck.extraction._baseline_candidates",
        directory / "baseline/code/candidates.py",
    )
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    replay = directory / "replay"
    replay.mkdir(exist_ok=False)
    cases, skipped, links = [], [], []
    for source in load(directory / "sources.json"):
        snapshot = Path(source["snapshot"])
        target = replay / snapshot.name
        target.mkdir()
        rows = jsonl(snapshot / "extractions.jsonl")
        records = {r["image_id"]: r for r in jsonl(snapshot / "manifest.jsonl")}
        after_rows = []
        for row in rows:
            identity = row["image_id"]
            if row["status"] != "ok":
                skipped.append(
                    {
                        "image_id": identity,
                        "source": source["source"],
                        "error": row.get("error"),
                    }
                )
                after_rows.append(row)
                continue
            adapted = load(snapshot / "inputs" / f"{identity}.json")
            groups = load(snapshot / "candidates" / f"{identity}.json")
            selection = row["final_selection"]
            before = baseline.resolve(selection, groups, adapted, normalize)
            after = resolve(selection, groups, adapted, normalize)
            a, b = before["seller_address"], after["seller_address"]
            if a["value_raw"] != row["fields"]["seller_address"]["value_raw"]:
                raise ValueError(f"Baseline address replay mismatch: {identity}")
            other_changes = [
                field
                for field in FIELDS
                if field != "seller_address" and before[field] != after[field]
            ]
            old_spans = sorted(json.dumps(s, sort_keys=True) for s in a["value_spans"])
            new_spans = sorted(json.dumps(s, sort_keys=True) for s in b["value_spans"])
            cases.append(
                {
                    "image_id": identity,
                    "source": source["source"],
                    "before": a["value_normalized"],
                    "after": b["value_normalized"],
                    "before_display": a["display_value"],
                    "after_display": b["display_value"],
                    "value_changed": a["value_normalized"] != b["value_normalized"],
                    "format_changed": a["display_value"] != b["display_value"],
                    "source_spans_preserved": old_spans == new_spans,
                    "other_field_changes": other_changes,
                    "before_status": a["status"],
                    "after_status": b["status"],
                    "reading_order": b["reading_order"],
                }
            )
            result = deepcopy(row)
            result["fields"]["seller_address"] = b
            result["raw_fields"]["seller_address"] = resolve(
                row["raw_model_selection"], groups, adapted, normalize
            )["seller_address"]
            result["replay"] = {"source": source["source"], "model_rerun": False}
            after_rows.append(result)
        (target / "extractions.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in after_rows),
            encoding="utf-8",
        )
        export_receipts(after_rows, target)
        images = {
            key: os.path.relpath(ROOT / "data/mcocr" / r["image_path"], target).replace(
                "\\", "/"
            )
            for key, r in records.items()
        }
        # Reuse immutable baseline evidence via relative links in the replay demo.
        for name in ["ocr", "responses"]:
            shutil.copytree(snapshot / name, target / name)
        (target / "report.md").write_text(
            "# Saved-selection replay\n\n"
            "This page reuses saved OCR and model selections; no model was run.\n\n"
            "See the [full report](../../report.md) and [before/after audit](../../audit.json).\n",
            encoding="utf-8",
        )
        render_demo(after_rows, target, images)
        links.append(
            f'<li><a href="replay/{target.name}/demo.html">{target.name}</a></li>'
        )

    summary = {
        "total_saved_receipts": len(cases) + len(skipped),
        "replayed": len(cases),
        "skipped_failed_baseline": len(skipped),
        "normalized_address_changes": sum(c["value_changed"] for c in cases),
        "display_changes": sum(c["format_changed"] for c in cases),
        "other_field_regressions": sum(bool(c["other_field_changes"]) for c in cases),
        "source_span_mismatches": sum(not c["source_spans_preserved"] for c in cases),
        "ambiguous_layouts": sum(c["reading_order"]["ambiguous"] for c in cases),
        "model_rerun": False,
    }
    write_json(
        directory / "audit.json",
        {"summary": summary, "cases": cases, "skipped": skipped},
    )
    report = [
        "# Address reading-order replay",
        "",
        "Uses saved OCR and model choices; this is not a fresh model run.",
        "",
        json.dumps(summary, indent=2),
        "",
    ]
    for case in cases:
        if case["format_changed"] or case["before_status"] != case["after_status"]:
            report.extend(
                [
                    f"## {case['image_id']}",
                    "",
                    f"Before: {case['before']}",
                    "",
                    f"After: {case['after']}",
                    "",
                    f"Lines: {case['reading_order']['line_region_ids']}",
                    "",
                ]
            )
    (directory / "audit.md").write_text("\n".join(report), encoding="utf-8")
    (directory / "replay.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Address replay</title><h1>Address replay — saved model selections</h1><pre>'
        + html.escape(json.dumps(summary, indent=2))
        + "</pre><ul>"
        + "".join(links)
        + "</ul>",
        encoding="utf-8",
    )
    print(json.dumps(summary))
    return int(
        bool(summary["other_field_regressions"] or summary["source_span_mismatches"])
    )


if __name__ == "__main__":
    raise SystemExit(main())
