"""Field-specific candidates with exact source spans."""

import re
import unicodedata
from itertools import pairwise

from .money import TOKEN
from .relations import labels as related_labels


def folded(text: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
        if not unicodedata.combining(c)
    )


def build(adapted: dict) -> dict:
    groups = {"seller_name": {}, "total_amount": {}, "transaction_datetime": {}}
    regions = adapted["mapping"]

    def add(field, spans, labels=None):
        prefix = {"seller_name": "N", "total_amount": "M", "transaction_datetime": "D"}[
            field
        ]
        identity = f"{prefix}{len(groups[field]) + 1:03d}"
        groups[field][identity] = {"value_spans": spans, "label_evidence": labels or []}

    def span(key, start, end):
        return {
            "region_id": key,
            "start": start,
            "end": end,
            "text": regions[key]["text"][start:end],
        }

    for key, r in regions.items():
        text = r["text"]
        add("seller_name", [span(key, 0, len(text))])
        for match in re.finditer(TOKEN, text):
            labels = related_labels(regions, key, match)
            add("total_amount", [span(key, *match.span())], labels)
        dates = list(re.finditer(r"(?<!\d)\d{1,2}[/-]\d{1,2}[/-]\d{4}(?!\d)", text))
        times = list(re.finditer(r"(?<!\d)\d{1,2}:\d{2}(?::\d{2})?(?!\d)", text))
        for date in dates:
            nearby = [
                t
                for t in times
                if abs(t.start() - date.end()) < 15 or abs(date.start() - t.end()) < 15
            ]
            spans = [span(key, *date.span())]
            if len(nearby) == 1:
                spans.append(span(key, *nearby[0].span()))
            elif not times:
                for other, v in regions.items():
                    if other == key:
                        continue
                    matches = list(
                        re.finditer(r"(?<!\d)\d{1,2}:\d{2}(?::\d{2})?(?!\d)", v["text"])
                    )
                    if len(matches) == 1 and abs(v["bbox"][1] - r["bbox"][1]) < 2 * max(
                        1, r["bbox"][3] - r["bbox"][1]
                    ):
                        spans.append(span(other, *matches[0].span()))
                        break
            add("transaction_datetime", spans, [{"region_id": key, "text": text}])
    # Keep all singleton name candidates; add only adjacent, aligned multiline alternatives.
    items = list(regions.items())
    for (ka, a), (kb, b) in pairwise(items):
        h = max(1, a["bbox"][3] - a["bbox"][1])
        if (
            0 <= b["bbox"][1] - a["bbox"][3] < h
            and abs(a["bbox"][0] - b["bbox"][0]) < h * 2
        ):
            add(
                "seller_name",
                [span(ka, 0, len(a["text"])), span(kb, 0, len(b["text"]))],
            )
    return groups


def schema(groups: dict, adapted: dict) -> dict:
    props = {field: {"enum": [None, *values]} for field, values in groups.items()}
    props["seller_address"] = {
        "type": "array",
        "items": {"enum": list(adapted["mapping"])},
    }
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


def resolve(selection: dict, groups: dict, adapted: dict, normalize) -> dict:
    expected = {*groups, "seller_address"}
    if not isinstance(selection, dict) or set(selection) != expected:
        raise ValueError("Wrong field keys")
    output = {}
    for field in expected:
        chosen = selection[field]
        if field == "seller_address":
            if (
                not isinstance(chosen, list)
                or any(
                    not isinstance(k, str) or k not in adapted["mapping"]
                    for k in chosen
                )
                or len(set(chosen)) != len(chosen)
            ):
                raise ValueError("Invalid address IDs")
            spans = [
                {
                    "region_id": k,
                    "start": 0,
                    "end": len(adapted["mapping"][k]["text"]),
                    "text": adapted["mapping"][k]["text"],
                }
                for k in chosen
            ]
            labels = []
        else:
            if chosen is not None and (
                not isinstance(chosen, str) or chosen not in groups[field]
            ):
                raise ValueError("Invalid scalar candidate")
            candidate = groups[field].get(
                chosen, {"value_spans": [], "label_evidence": []}
            )
            spans = candidate["value_spans"]
            labels = candidate["label_evidence"]
        for s in spans:
            if (
                adapted["mapping"][s["region_id"]]["text"][s["start"] : s["end"]]
                != s["text"]
            ):
                raise ValueError("Invalid exact span")
        ids = list(dict.fromkeys(s["region_id"] for s in spans))
        raw = ("\n" if field in ("seller_address", "seller_name") else " ").join(
            s["text"] for s in spans
        ) or None
        value, issues = normalize(field, raw) if raw else (None, [])
        precision = None
        display = raw
        if field == "transaction_datetime" and value:
            precision = (
                "second"
                if any(re.search(r"\d+:\d+:\d+", s["text"]) for s in spans)
                else "minute"
                if ":" in raw
                else "date"
            )
            if precision == "minute":
                value = value[:16]
            display = " ".join(s["text"] for s in spans)
        if adapted["ocr_status"] != "ok":
            issues.append("partial_ocr")
        evidence = [adapted["mapping"][k] for k in ids]
        scores = [v["confidence"] for v in evidence]
        output[field] = {
            "value_raw": raw,
            "value_normalized": value,
            "display_value": display,
            "precision": precision,
            "value_spans": spans,
            "evidence_region_ids": ids,
            "source_candidate_ids": [v["source_candidate_id"] for v in evidence],
            "evidence": evidence,
            "label_evidence": labels,
            "selection_confidence": None,
            "ocr_confidence": min(scores)
            if scores and all(s is not None for s in scores)
            else None,
            "issues": issues,
            "status": "not_found"
            if raw is None
            else "needs_review"
            if issues
            else "ok",
        }
    return output
