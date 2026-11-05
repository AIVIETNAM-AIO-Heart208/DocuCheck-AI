#!/usr/bin/env python3
"""Build local, deterministic crop-error contact sheets for visual review.

Selection labels are heuristics, not verified causes. Add reviewer decisions to
the generated JSON/CSV separately after inspecting the images.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import random
import re
import shutil
import sys
import textwrap
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from docucheck.data.loader import resolve_dataset_root  # noqa: E402
from docucheck.evaluation.metrics import normalize_text  # noqa: E402
from docucheck.ocr.inference import load_manifest  # noqa: E402


def without_accents(text):
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c)).replace("đ", "d")


def select_cases(details, records):
    errors = sorted((r for r in details if r["char_errors"] > 0), key=lambda r: r["image_id"])
    rng = random.Random(42)
    groups = [
        ("empty_prediction", lambda r, gt, pred: not pred),
        ("accent_candidate", lambda r, gt, pred: bool(pred) and without_accents(gt) == without_accents(pred)),
        ("spacing_candidate", lambda r, gt, pred: gt.replace(" ", "") == pred.replace(" ", "")),
        ("numeric_text", lambda r, gt, pred: bool(re.search(r"\d", gt)) and len(re.findall(r"\d", gt)) >= len(gt) / 2),
        ("small_text", lambda r, gt, pred: records[r["image_id"]]["image_height"] <= 20),
        ("mixed_high_error", lambda r, gt, pred: r["cer"] >= .5 and bool(pred)),
    ]
    chosen = []
    used = set()
    for group, predicate in groups:
        candidates = [r for r in errors if r["image_id"] not in used
                      and predicate(r, normalize_text(r["text_gt"]), normalize_text(r["text_pred"]))]
        for row in rng.sample(candidates, min(4, len(candidates))):
            chosen.append({**row, "selection_group": group})
            used.add(row["image_id"])
    candidates = [r for r in errors if r["image_id"] not in used]
    for row in rng.sample(candidates, min(24 - len(chosen), len(candidates))):
        chosen.append({**row, "selection_group": "additional_error"})
    return chosen


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "data/processed/recognition_manifest.jsonl")
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--dataset-root", default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--font", type=Path, default=Path("C:/Windows/Fonts/arial.ttf"))
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "review_cases.json").exists():
        parser.error("Review already exists; use a fresh directory to preserve reviewer notes.")
    crops_dir = output / "crops"
    crops_dir.mkdir(exist_ok=True)
    root = resolve_dataset_root(args.dataset_root)
    records = {r["image_id"]: r for r in load_manifest(args.manifest)}
    cases = select_cases(load_manifest(args.metrics), records)
    font = ImageFont.truetype(str(args.font), 21)
    small_font = ImageFont.truetype(str(args.font), 18)
    cards = []
    for i, case in enumerate(cases):
        row = records[case["image_id"]]
        src = root / row["image_path"]
        copied = crops_dir / f"{i+1:02d}{src.suffix}"
        shutil.copyfile(src, copied)
        case.update({"case_number": i + 1, "image_path": row["image_path"],
                     "original_width": row["image_width"], "original_height": row["image_height"],
                     "local_image": copied.relative_to(output).as_posix(),
                     "review_status": "pending", "reviewer": None, "cause": None,
                     "error_tags": [], "visual_notes": None})
        card = Image.new("RGB", (800, 450), "white")
        draw = ImageDraw.Draw(card)
        draw.text((16, 10), f"{i+1:02d} | {case['selection_group']} | {row['image_width']}x{row['image_height']}", fill="black", font=font)
        with Image.open(src) as image:
            tile = ImageOps.contain(image.convert("RGB"), (760, 180))
            card.paste(tile, (16, 48))
        y = 238
        for prefix, value in (("GT: ", case["text_gt"]), ("OCR: ", case["text_pred"] or "[EMPTY]")):
            lines = textwrap.wrap(prefix + value, width=62) or [prefix]
            draw.multiline_text((16, y), "\n".join(lines), fill="black", font=font, spacing=4)
            y += len(lines) * 27 + 6
        draw.text((16, 420), f"CER {case['cer']:.4f} | WER {case['wer']:.4f} | {case['split']} | display enlarged", fill="#555555", font=small_font)
        cards.append(card)
    for offset in range(0, len(cards), 4):
        sheet = Image.new("RGB", (1600, 900), "#eeeeee")
        for j, card in enumerate(cards[offset:offset + 4]):
            sheet.paste(card, ((j % 2) * 800, (j // 2) * 450))
        sheet.save(output / f"contact_sheet_{offset//4+1:02d}.png")
    (output / "review_cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output / "review_cases.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = ["case_number", "image_id", "split", "selection_group", "text_gt", "text_pred",
                  "cer", "wer", "local_image", "review_status", "reviewer", "cause", "visual_notes"]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(cases)
    sheets = sorted(output.glob("contact_sheet_*.png"))
    markup = "\n".join(f'<img src="{html.escape(p.name)}" style="width:100%;max-width:1600px" alt="Error cases">' for p in sheets)
    (output / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Recognition error review</title>'
        '<body style="font-family:Arial;background:#eee"><h1>Recognition error review</h1>'
        '<p>Local dataset evidence. Selection groups are heuristics; see review_cases.json for review decisions.</p>'
        + markup + '</body></html>', encoding="utf-8")
    print(f"Prepared {len(cases)} cases and {len(sheets)} contact sheets at {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
