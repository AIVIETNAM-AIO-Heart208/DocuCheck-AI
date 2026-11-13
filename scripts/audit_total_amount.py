"""Replay and CUDA comparison of saved OCR, without exposing GT to inference."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from docucheck.extraction.candidates import build, resolve
from docucheck.extraction.invoice_total import annotate, guard
from docucheck.extraction.qwen import normalize, write_json


def rows(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def signature(candidate):
    return [
        (s["region_id"], s["start"], s["end"], s["text"])
        for s in candidate["value_spans"]
    ]


def expected(record):
    # Independent annotation reader; deliberately does not call product normalizer.
    texts = [
        r["text_raw"]
        for r in record["regions"]
        if r.get("canonical_field") == "total_amount"
    ]
    amounts = set()
    for text in texts:
        for token in re.findall(r"\d+(?:[.,]\d+)*", text):
            if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+|\d+", token):
                amounts.add(int(token.replace(",", "").replace(".", "")))
            elif re.fullmatch(r"\d{1,3}(?:,\d{3})+\.00", token):
                amounts.add(int(token[:-3].replace(",", "")))
    return (next(iter(amounts)) if len(amounts) == 1 else None), texts


def audit(directory, gpu=False):
    sources = [Path(p) for p in json.loads((directory / "sources.json").read_text())]
    entries = []
    links = []
    for index, source in enumerate(sources):
        target = directory / f"batch_{index + 1:02d}"
        if gpu:
            target.mkdir(exist_ok=True)
            shutil.copy2(source / "manifest.jsonl", target / "manifest.jsonl")
            shutil.copytree(source / "ocr", target / "ocr", dirs_exist_ok=True)
            subprocess.run(
                [
                    sys.executable,
                    "scripts/demo_ocr_qwen.py",
                    "--manifest",
                    str(target / "manifest.jsonl"),
                    "--output-dir",
                    str(target),
                    "--reuse-ocr",
                ],
                check=True,
                cwd=ROOT,
            )
        after = (
            {r["image_id"]: r for r in rows(target / "extractions.jsonl")}
            if (target / "extractions.jsonl").exists()
            else {}
        )
        records = {r["image_id"]: r for r in rows(source / "manifest.jsonl")}
        for before in rows(source / "extractions.jsonl"):
            key = before["image_id"]
            adapted = json.loads(
                (source / "inputs" / f"{key}.json").read_text(encoding="utf-8")
            )
            old = json.loads(
                (source / "candidates" / f"{key}.json").read_text(encoding="utf-8")
            )
            groups = build(adapted)
            annotate(groups)
            selection = dict(before["raw_model_selection"])
            chosen = selection["total_amount"]
            matches = (
                [
                    k
                    for k, c in groups["total_amount"].items()
                    if signature(c) == signature(old["total_amount"][chosen])
                ]
                if chosen
                else []
            )
            selection["total_amount"] = matches[0] if len(matches) == 1 else None
            final, decision = guard(selection, groups)
            replay = resolve(final, groups, adapted, normalize)["total_amount"][
                "value_normalized"
            ]
            raw_before = resolve(
                before["raw_model_selection"], old, adapted, normalize
            )["total_amount"]["value_normalized"]
            truth, annotations = expected(records[key])
            current = after.get(key, {})
            current_fields = current.get("fields", {})
            money = current_fields.get("total_amount", {})
            raw = (
                current.get("raw_fields", {})
                .get("total_amount", {})
                .get("value_normalized")
            )
            changed = {
                f: {
                    "before": v["value_normalized"],
                    "after": current_fields.get(f, {}).get("value_normalized"),
                }
                for f, v in before["fields"].items()
                if f != "total_amount"
                and current
                and v["value_normalized"]
                != current_fields.get(f, {}).get("value_normalized")
            }
            entry = {
                "image_id": key,
                "source": str(source),
                "expected": truth,
                "annotations": annotations,
                "baseline_raw": raw_before,
                "baseline_final": before["fields"]["total_amount"]["value_normalized"],
                "replay": replay,
                "replay_decision": decision,
                "remap_unique": chosen is None or len(matches) == 1,
                "cuda_raw": raw,
                "cuda_final": money.get("value_normalized"),
                "cuda_status": current.get("status", "not_run"),
                "cuda_decision": current.get("total_amount_decision"),
                "other_field_changes": changed,
                "candidate_contains_expected": any(
                    c.get("parsed_amount") == truth
                    for c in groups["total_amount"].values()
                )
                if truth is not None
                else None,
                "ocr_sha256": hashlib.sha256(
                    (source / "ocr/predictions.jsonl").read_bytes()
                ).hexdigest(),
            }
            entries.append(entry)
            write_json(
                directory / "replay" / f"{key}.json",
                {"audit": entry, "candidates": groups},
            )
        if after:
            links.append(
                f'<p><a href="{target.name}/demo.html">Batch {index + 1}</a></p>'
            )
    summary = {
        name: sum(
            e[name] == e["expected"] for e in entries if e["expected"] is not None
        )
        for name in (
            "baseline_raw",
            "baseline_final",
            "replay",
            "cuda_raw",
            "cuda_final",
        )
    }
    summary.update(
        {
            "scorable": sum(e["expected"] is not None for e in entries),
            "cuda_executed": sum(e["cuda_status"] == "ok" for e in entries),
            "baseline_guard_harmed": sum(
                e["baseline_raw"] == e["expected"]
                and e["baseline_final"] != e["expected"]
                for e in entries
                if e["expected"] is not None
            ),
            "cuda_guard_harmed": sum(
                e["cuda_raw"] == e["expected"] and e["cuda_final"] != e["expected"]
                for e in entries
                if e["expected"] is not None
            ),
            "other_field_changes": sum(len(e["other_field_changes"]) for e in entries),
        }
    )
    write_json(directory / "audit.json", {"summary": summary, "entries": entries})
    header = "| Image | Expected | Baseline raw | Baseline final | Replay | CUDA raw | CUDA final |\n|---|---:|---:|---:|---:|---:|---:|\n"
    table = header + "\n".join(
        "| "
        + " | ".join(
            str(e[k])
            for k in (
                "image_id",
                "expected",
                "baseline_raw",
                "baseline_final",
                "replay",
                "cuda_raw",
                "cuda_final",
            )
        )
        + " |"
        for e in entries
    )
    (directory / "report.md").write_text(
        "# Audit total_amount\n\n"
        + json.dumps(summary, indent=2)
        + "\n\n"
        + table
        + "\n\nExpected uses independent annotation parsing; image/policy review is required for disputed annotations. Baseline source-code provenance is not assumed. OCR is cached. These are development receipts, not a dataset benchmark.\n",
        encoding="utf-8",
    )
    (directory / "index.html").write_text(
        '<meta charset="utf-8"><h1>Audit OCR → Qwen</h1><a href="report.md">Report</a> <a href="audit.json">Audit JSON</a>'
        + "".join(links),
        encoding="utf-8",
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--gpu", action="store_true")
    args = parser.parse_args()
    audit(args.directory, args.gpu)
