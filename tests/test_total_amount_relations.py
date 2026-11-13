"""Integration regressions using geometry rather than pre-labelled money mocks."""

import pytest

from docucheck.extraction.candidates import build
from docucheck.extraction.invoice_total import annotate, guard, role
from docucheck.extraction.money import parse


def region(text, x, y, width=100, slope=0):
    return {
        "text": text,
        "bbox": [x, y, x + width, y + 16],
        "polygon": [
            [x, y],
            [x + width, y + slope * width],
            [x + width, y + 16 + slope * width],
            [x, y + 16],
        ],
    }


@pytest.mark.parametrize("scale,reverse", [(1, False), (2, True), (0.5, True)])
def test_total_and_discount_rows_do_not_contaminate_each_other(scale, reverse):
    mapping = {
        "L1": region("TỔNG TIỀN PHẢI T.TOÁN", 10, 100),
        "V1": region("49.500", 300, 100),
        "L2": region("TỔNG TIẾN Ã GIẢM", 10, 120),
        "V2": region("0", 300, 120),
        "L3": region("TIỀN KHÁCH TRẢ", 10, 140),
        "V3": region("100.000", 300, 140),
    }
    for r in mapping.values():
        r["polygon"] = [[(x + 20) * scale, (y + 30) * scale] for x, y in r["polygon"]]
    if reverse:
        mapping = dict(reversed(list(mapping.items())))
    groups = build({"mapping": mapping})
    annotate(groups)
    key = next(
        k for k, c in groups["total_amount"].items() if c["parsed_amount"] == 49500
    )
    result, _ = guard({"total_amount": key}, groups)
    assert result["total_amount"] == key
    assert (
        len(
            [c for c in groups["total_amount"].values() if c["role"] == "invoice_total"]
        )
        == 1
    )


def test_quantity_column_is_not_another_total():
    groups = build(
        {
            "mapping": {
                "L": region("Tổng cộng", 10, 100),
                "Q": region("6", 180, 100),
                "V": region("190.000", 350, 100),
            }
        }
    )
    annotate(groups)
    assert [
        c["parsed_amount"]
        for c in groups["total_amount"].values()
        if c["role"] == "invoice_total"
    ] == [190000]


@pytest.mark.parametrize(
    "text,value",
    [
        ("27,200.00", 27200),
        ("27.200,00", 27200),
        ("1111,990", None),
        ("12,50", None),
        ("0", 0),
        ("-25,000", -25000),
        ("9,132,000", 9132000),
    ],
)
def test_parser_preserves_value_and_refuses_ambiguous_format(text, value):
    assert parse(text) == value


def test_specific_discount_precedes_generic_total():
    assert role("TỔNG TIẾN Ã GIẢM") == "discount"
    assert role("Khách phải trả") == "invoice_total"
    assert role("Phải trả sau đặt cọc") == "balance_due"


def test_cash_change_contradiction_abstains_without_inventing_amount():
    mapping = {}
    for i, (label, amount) in enumerate(
        [
            ("Tổng cộng", "9,132,000"),
            ("Tiền khách trả", "500,000"),
            ("Tiền trả lại", "368,000"),
        ]
    ):
        mapping[f"L{i}"] = region(label, 10, i * 40)
        mapping[f"V{i}"] = region(amount, 300, i * 40)
    groups = build({"mapping": mapping})
    annotate(groups)
    chosen = next(
        k for k, c in groups["total_amount"].items() if c["parsed_amount"] == 9132000
    )
    final, decision = guard({"total_amount": chosen}, groups)
    assert final["total_amount"] is None
    assert decision["reason"] == "invoice_arithmetic_conflict"


@pytest.mark.parametrize("cash,change", [("200,000", "98,800"), ("100,100", "0")])
def test_misread_change_does_not_reject_total_below_cash(cash, change):
    mapping = {}
    for i, (label, amount) in enumerate(
        [
            ("Tổng cộng", "101,100"),
            ("Tiền khách trả", cash),
            ("Tiền trả lại", change),
        ]
    ):
        mapping[f"L{i}"] = region(label, 10, i * 40)
        mapping[f"V{i}"] = region(amount, 300, i * 40)
    groups = build({"mapping": mapping})
    annotate(groups)
    chosen = next(
        k for k, c in groups["total_amount"].items() if c["parsed_amount"] == 101100
    )
    assert guard({"total_amount": chosen}, groups)[0]["total_amount"] == chosen
