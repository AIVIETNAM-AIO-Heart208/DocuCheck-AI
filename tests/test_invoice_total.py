"""Invoice total semantics independent of model and receipt-specific IDs."""

import pytest

from docucheck.extraction.invoice_total import annotate, guard, role
from docucheck.extraction.qwen import normalize


def candidates(rows):
    values = {
        f"A{i}": {
            "value_spans": [{"text": str(amount)}],
            "label_evidence": [{"text": label}],
        }
        for i, (label, amount) in enumerate(rows)
    }
    groups = {"total_amount": values}
    annotate(groups)
    return groups


@pytest.mark.parametrize(
    "rows",
    [
        [("Tổng phải trả", 840000), ("Đã thanh toán", 300000), ("Còn lại", 540000)],
        [("Tổng tiền", 78000), ("Khách đưa", 100000), ("Tiền trả lại", 22000)],
        [("Tổng phải trả", 100000), ("Tổng tiền hàng", 120000), ("Giảm giá", 20000)],
        [("Tổng tiền", 90000), ("Tiền đặt cọc", 90000), ("Còn lại", 90000)],
        [("Tong tien", 150000), ("Tiền mặt", 50000), ("Tiền thẻ", 100000)],
    ],
)
def test_guard_selects_explicit_total_not_payment_or_max(rows):
    result, audit = guard({"total_amount": "A1"}, candidates(rows))
    assert result["total_amount"] == "A0"
    assert audit["raw_candidate_id"] == "A1"
    assert audit["decision_source"] == "rule"


def test_no_total_or_conflict_requires_review():
    assert (
        guard({"total_amount": "A0"}, candidates([("Còn lại", 400)]))[0]["total_amount"]
        is None
    )
    assert (
        guard(
            {"total_amount": "A0"}, candidates([("Tổng tiền", 400), ("Tổng cộng", 500)])
        )[0]["total_amount"]
        is None
    )


def test_role_not_single_word():
    assert role("Tổng số lượng") == "unknown"
    assert role("Tổng tiền hàng") == "subtotal"
    assert role("Tiền khách trả") == "unknown"
    assert role("Phải trả sau khi đã trả đặt cọc") == "balance_due"


@pytest.mark.parametrize(
    "text,value",
    [("0", 0), ("-25,000", -25000), ("650,000\n650,000", None), ("12,50", None)],
)
def test_money_no_partial_or_sign_loss(text, value):
    assert normalize("total_amount", text)[0] == value


def test_unknown_id_rejected():
    with pytest.raises(ValueError):
        guard({"total_amount": "BAD"}, candidates([("Tổng tiền", 0)]))


def test_malformed_grouping_is_retained_but_not_used_as_confirmed_total():
    groups = candidates([("Tổng cộng", "111,990"), ("Tổng tiền", "1111,990")])
    assert groups["total_amount"]["A1"]["role_issue"] == "invalid_amount_format"
    result, _ = guard({"total_amount": "A0"}, groups)
    assert result["total_amount"] == "A0"
