"""Conservative invoice-total role inference and auditable conflict guard."""

import re
import unicodedata

from .money import parse


def fold(text: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
        if not unicodedata.combining(c)
    )


def role(text: str) -> str:
    text = fold(text)
    patterns = [
        ("balance_due", r"con lai|con no|du no|sau.*(?:dat coc|da tra)"),
        ("change", r"tra lai|tien thua"),
        ("deposit", r"dat coc|dat hang|tam ung"),
        ("paid_amount", r"da thanh toan|da tra|khach thanh toan"),
        ("tendered_amount", r"khach dua|tien mat|tien the"),
        ("discount", r"chiet khau|giam gia|(?:da |a )?giam"),
        ("subtotal", r"(?:tong|cong) tien hang|tam tinh"),
        (
            "invoice_total",
            r"(?:tong\s+(?:so\s+)?(?:phai tra|thanh toan|cong|tien(?:\s+phai)?)|khach phai tra)\b",
        ),
        ("tax_fee", r"thue|vat|phi dich vu"),
    ]
    return next(
        (name for name, pattern in patterns if re.search(pattern, text)), "unknown"
    )


def annotate(groups: dict) -> None:
    for candidate in groups["total_amount"].values():
        raw = "".join(s["text"] for s in candidate["value_spans"])
        valid = parse(raw) is not None
        roles = {role(v["text"]) for v in candidate["label_evidence"]} - {"unknown"}
        candidate["role"] = (
            next(iter(roles)) if len(roles) == 1 and valid else "unknown"
        )
        candidate["parsed_amount"] = parse(raw)
        candidate["role_evidence"] = sorted(roles)
        candidate["role_issue"] = (
            "invalid_amount_format"
            if not valid
            else "conflicting_labels"
            if len(roles) > 1
            else None
        )

    by_label = {}
    for key, c in groups["total_amount"].items():
        if c["role"] == "invoice_total" and c["label_evidence"]:
            label = c["label_evidence"][0].get("region_id")
            if label is not None:
                by_label.setdefault(label, []).append((key, c))
    for alternatives in by_label.values():
        if len(alternatives) > 1:
            formatted = [
                (k, c)
                for k, c in alternatives
                if re.search(r"[.,]", c["value_spans"][0]["text"])
            ]
            if len(formatted) == 1:
                for key, c in alternatives:
                    if key != formatted[0][0]:
                        c["role"] = "unknown"
                        c["role_issue"] = "competing_quantity_column"


def guard(selection: dict, groups: dict) -> tuple[dict, dict]:
    chosen = selection["total_amount"]
    values = groups["total_amount"]
    if chosen is not None and (not isinstance(chosen, str) or chosen not in values):
        raise ValueError("Unknown money candidate")
    totals = [k for k, v in values.items() if v["role"] == "invoice_total"]
    result = dict(selection)
    reason = None
    if chosen is not None and values[chosen]["role"] == "invoice_total":
        amounts = {values[k]["parsed_amount"] for k in totals}
        if len(amounts) > 1:
            result["total_amount"] = None
            reason = "conflicting_invoice_totals"
    elif (
        not totals
        and chosen is not None
        and values[chosen]["role"] == "subtotal"
        and not any(v["role"] in {"discount", "tax_fee"} for v in values.values())
    ):
        reason = "subtotal_without_adjustments"
    elif totals and len({values[k]["parsed_amount"] for k in totals}) == 1:
        result["total_amount"] = totals[0]
        reason = "unique_direct_invoice_total"
    else:
        result["total_amount"] = None
        reason = "invoice_total_not_unambiguous"
    final = values.get(result["total_amount"])
    changes = {v["parsed_amount"] for v in values.values() if v["role"] == "change"}
    cash = {
        v["parsed_amount"]
        for v in values.values()
        if any("tien khach tra" in fold(label["text"]) for label in v["label_evidence"])
    }
    tendered = {
        v["parsed_amount"] for v in values.values() if v["role"] == "tendered_amount"
    }
    if len(tendered) == 1:
        cash = tendered
    # A printed change row makes cash tendered unambiguous. Use arithmetic only
    # to reject contradictions, never to manufacture a replacement OCR value.
    if (
        final
        and len(changes) == len(cash) == 1
        and not any(v["role"] in {"deposit", "paid_amount"} for v in values.values())
        and final["parsed_amount"] > next(iter(cash)) >= 0
        and next(iter(changes)) > 0
        and len(tendered) <= 1
    ):
        result["total_amount"] = None
        reason = "invoice_arithmetic_conflict"
    return result, {
        "raw_candidate_id": chosen,
        "final_candidate_id": result["total_amount"],
        "decision_source": "model" if result == selection else "rule",
        "reason": reason,
        "direct_total_candidates": totals,
    }
