"""Audit saved invoice totals against manually reviewed reference values."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from docucheck.extraction.qwen import write_json

# Evaluation only: never imported by inference. References reviewed from annotations.
REFERENCE = {
    "06f4a47f229eed1d676fab46": 90996,
    "0874556a37c06749b6534fb8": 1300000,
    "093729140a242921ebbfb5b5": 108000,
    "2a7306b34813fe5196db7fff": 111990,
    "e43df013500d0d9c7d6874b6": 101100,
}


def main(directory: Path):
    previous = ROOT / "outputs/ocr_to_qwen/field_selection_fix/run_20261113"
    entries = []
    for batch, baseline in [("old_v2", "old_v2"), ("new_v2", "new")]:
        p = directory / batch
        old = {
            r["image_id"]: r
            for r in map(
                json.loads,
                (previous / baseline / "extractions.jsonl")
                .read_text(encoding="utf-8")
                .splitlines(),
            )
        }
        assert (p / "ocr/predictions.jsonl").read_bytes() == (
            previous / baseline / "ocr/predictions.jsonl"
        ).read_bytes()
        for row in map(
            json.loads,
            (p / "extractions.jsonl").read_text(encoding="utf-8").splitlines(),
        ):
            identity = row["image_id"]
            groups = json.loads(
                (p / "candidates" / f"{identity}.json").read_text(encoding="utf-8")
            )
            adapted = json.loads(
                (p / "inputs" / f"{identity}.json").read_text(encoding="utf-8")
            )
            decision = row["total_amount_decision"]
            raw = groups["total_amount"].get(decision["raw_candidate_id"])
            expected = REFERENCE[identity]
            value = row["fields"]["total_amount"]["value_normalized"]
            entries.append(
                {
                    "image_id": identity,
                    "expected_total": expected,
                    "before": old[identity]["fields"]["total_amount"][
                        "value_normalized"
                    ],
                    "raw_model_candidate_id": decision["raw_candidate_id"],
                    "raw_model_candidate": raw,
                    "final": value,
                    "decision": decision,
                    "match": value == expected,
                    "raw_model_match": raw is not None
                    and raw.get("parsed_amount") == expected,
                    "expected_present_in_candidates": any(
                        v.get("parsed_amount") == expected
                        for v in groups["total_amount"].values()
                    ),
                    "excluded_regions": len(adapted["excluded"]),
                    "other_field_changes": {
                        k: {
                            "before": v["value_normalized"],
                            "after": row["fields"][k]["value_normalized"],
                        }
                        for k, v in old[identity]["fields"].items()
                        if k != "total_amount"
                        and v["value_normalized"]
                        != row["fields"][k]["value_normalized"]
                    },
                    "ocr_sha256": hashlib.sha256(
                        (p / "ocr/predictions.jsonl").read_bytes()
                    ).hexdigest(),
                }
            )
    write_json(
        directory / "audit.json",
        {
            "expected_source": "Manually reviewed invoice total annotation values; independent of product money parser",
            "entries": entries,
            "money_correct": sum(e["match"] for e in entries),
            "raw_model_money_correct": sum(e["raw_model_match"] for e in entries),
            "denominator": len(REFERENCE),
        },
    )
    print(
        json.dumps(
            {
                "correct": sum(e["match"] for e in entries),
                "other_changes": [e["other_field_changes"] for e in entries],
            }
        )
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
