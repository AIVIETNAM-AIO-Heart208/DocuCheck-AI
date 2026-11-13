"""Regression checks for scalar selection and exact OCR spans."""

import pytest

from docucheck.extraction.candidates import build, resolve, schema
from docucheck.extraction.qwen import adapt, normalize


def source(texts):
    return adapt(
        {
            "image_id": "test",
            "status": "ok",
            "predictions": [
                {
                    "text": t,
                    "candidate_id": str(i),
                    "polygon": [
                        [0, i * 20],
                        [190, i * 20],
                        [190, i * 20 + 15],
                        [0, i * 20 + 15],
                    ],
                    "recognition_confidence": 0.1,
                }
                for i, t in enumerate(texts)
            ],
        },
        200,
        300,
    )


def test_datetime_value_excludes_transaction_id():
    a = source(["Số GD: 000AB2212008002426 Ngày: 09/08/2020-21:20"])
    groups = build(a)
    selection = {
        "seller_name": None,
        "seller_address": [],
        "transaction_datetime": "D001",
        "total_amount": None,
    }
    value = resolve(selection, groups, a, normalize)["transaction_datetime"]
    assert value["display_value"] == "09/08/2020 21:20"
    assert value["value_normalized"] == "2020-08-09T21:20"
    assert "Số GD" in value["evidence"][0]["text"]
    assert all(
        a["mapping"][s["region_id"]]["text"][s["start"] : s["end"]] == s["text"]
        for s in value["value_spans"]
    )


def test_equal_amounts_are_not_combined():
    a = source(["90,996", "90,996", "90,996"])
    groups = build(a)
    assert len(groups["total_amount"]) == 3
    selection = {
        "seller_name": None,
        "seller_address": [],
        "transaction_datetime": None,
        "total_amount": "M002",
    }
    assert (
        resolve(selection, groups, a, normalize)["total_amount"]["value_normalized"]
        == 90996
    )
    selection["total_amount"] = ["M001", "M002"]
    with pytest.raises(ValueError):
        resolve(selection, groups, a, normalize)


def test_multiline_names_keep_singletons_and_no_word_deduplication():
    a = source(["COCO COCO", "SHOP"])
    groups = build(a)
    assert any(len(c["value_spans"]) == 2 for c in groups["seller_name"].values())
    assert groups["seller_name"]["N001"]["value_spans"][0]["text"] == "COCO COCO"
    assert "enum" in schema(groups, a)["properties"]["seller_name"]


def test_two_dates_remain_separate_candidates():
    groups = build(source(["Ngày: 01/01/2020; HSD: 02/02/2020"]))
    assert len(groups["transaction_datetime"]) == 2


def test_wrong_span_is_rejected():
    a = source(["Runa Corner"])
    groups = build(a)
    groups["seller_name"]["N001"]["value_spans"][0]["text"] = "invented"
    with pytest.raises(ValueError):
        resolve(
            {
                "seller_name": "N001",
                "seller_address": [],
                "transaction_datetime": None,
                "total_amount": None,
            },
            groups,
            a,
            normalize,
        )
