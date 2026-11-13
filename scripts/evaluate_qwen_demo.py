"""Evaluate saved predictions after inference; never expose annotations to Qwen."""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from docucheck.extraction.qwen import FIELDS, normalize, write_json


def comparable(value):
    return re.sub(
        r"[^\w]",
        "",
        unicodedata.normalize("NFKC", str("" if value is None else value)).casefold(),
    )


def evaluate(directory):
    records = {
        r["image_id"]: r
        for r in map(
            json.loads,
            (directory / "manifest.jsonl").read_text(encoding="utf-8").splitlines(),
        )
    }
    results = list(
        map(
            json.loads,
            (directory / "extractions.jsonl").read_text(encoding="utf-8").splitlines(),
        )
    )
    entries = []
    for row in results:
        record = records[row["image_id"]]
        adapted = json.loads(
            (directory / "inputs" / f"{row['image_id']}.json").read_text(
                encoding="utf-8"
            )
        )
        alltext = " ".join(r["text"] for r in adapted["regions"])
        for field in FIELDS:
            regions = [
                r for r in record["regions"] if r.get("canonical_field") == field
            ]
            texts = [r["text_raw"] for r in regions]
            expected = "\n".join(texts)
            issue = None
            if field == "total_amount":
                candidates = [normalize(field, t)[0] for t in texts]
                candidates = list(dict.fromkeys(x for x in candidates if x is not None))
                expected = candidates[0] if len(candidates) == 1 else None
                if expected is None:
                    issue = "GT contains no unique amount"
            elif field == "transaction_datetime":
                expected = normalize(field, expected)[0]
            if not regions or expected is None:
                issue = issue or "Missing/unparseable GT"
            prediction = row.get("fields", {}).get(field, {})
            predicted = prediction.get("value_normalized")
            match = None if issue else comparable(predicted) == comparable(expected)
            if (
                field == "transaction_datetime"
                and isinstance(predicted, str)
                and isinstance(expected, str)
            ):
                match = (
                    predicted.removesuffix(":00") == expected.removesuffix(":00")
                    if not issue
                    else None
                )
            coverage = all(
                comparable(t) in comparable(alltext) for t in texts if comparable(t)
            )
            entries.append(
                {
                    "image_id": row["image_id"],
                    "field": field,
                    "annotation_regions": regions,
                    "expected": expected,
                    "predicted_raw": prediction.get("value_raw"),
                    "predicted_normalized": predicted,
                    "match": match,
                    "unscorable_reason": issue,
                    "all_GT_text_present_in_OCR_payload": coverage,
                    "excluded_regions": len(adapted["excluded"]),
                    "error_stage": None
                    if match
                    else "unscorable"
                    if issue
                    else "selection_or_OCR; inspect evidence",
                    "evidence_region_ids": prediction.get("evidence_region_ids"),
                }
            )
    report = {
        "policy": "Names/address: NFKC casefold and ignore punctuation/whitespace; preserve accents and all components. Datetime: ISO; missing time not invented. Amount: unique parseable annotated numeric region; no concatenating labels. No semantic substring credit for name duplication.",
        "correct_fields": sum(e["match"] is True for e in entries),
        "scorable_fields": sum(e["match"] is not None for e in entries),
        "unscorable_fields": sum(e["match"] is None for e in entries),
        "fully_correct_receipts": sum(
            all(e["match"] is True for e in entries if e["image_id"] == r["image_id"])
            for r in results
        ),
        "entries": entries,
        "limitations": [
            "Two preselected internal_dev images; not an accuracy benchmark",
            "See runtime.json ocr_reused for whether OCR was freshly run",
            "Evidence coverage is strict text containment diagnostic, not geometric OCR accuracy",
        ],
    }
    write_json(directory / "evaluation.json", report)
    lines = [
        "# OCR → Qwen: đánh giá demo",
        "",
        report["policy"],
        "",
        f"Đúng {report['correct_fields']}/{report['scorable_fields']} field; {report['fully_correct_receipts']}/{len(records)} ảnh đúng đủ 4 field.",
        "",
        "| Image | Field | Expected | Predicted | Match |",
        "|---|---|---|---|---|",
    ]
    for e in entries:
        values = [
            e["image_id"],
            e["field"],
            str(e["expected"]),
            str(e["predicted_normalized"]),
            str(e["match"]),
        ]
        lines.append(
            "| "
            + " | ".join(v.replace("\n", " / ").replace("|", "\\|") for v in values)
            + " |"
        )
    lines.extend(
        [
            "",
            "## Phân loại lỗi",
            "",
            (
                "Xem expected/predicted và annotation gốc trong evaluation.json. "
                "Bằng chứng OCR và mapping lưu trong inputs/. Kiểm tra riêng OCR, lựa chọn và chuẩn hóa."
            ),
            "",
            "## Giới hạn",
            "",
            (
                "Đây là smoke demo trên 2 ảnh internal_dev, chưa phải benchmark toàn dataset. "
                "Không suy ra tốt hơn LiLT/JEV. Bộ nhớ runtime.json là số lấy mẫu, không phải peak tuyệt đối. "
                "Kết quả kiểm thử ở ../pytest_final.txt."
            ),
        ]
    )
    (directory / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    result = evaluate(args.directory)
    print(result["correct_fields"], result["scorable_fields"])
