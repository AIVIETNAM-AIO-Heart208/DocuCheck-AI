import json

import pytest

from docucheck.extraction.qwen import (
    FIELDS,
    QwenClient,
    adapt,
    normalize,
    render_demo,
    validate,
)


def receipt():
    return {
        "image_id": "a",
        "status": "ok",
        "regions": [{"text_raw": "SECRET_GT"}],
        "predictions": [
            {
                "candidate_id": "a:1",
                "text": "Địa chỉ <script>",
                "polygon": [[0, 0], [50, 0], [50, 10], [0, 10]],
                "recognition_confidence": 0.01,
            },
            {
                "candidate_id": "a:2",
                "text": "Hà Nội",
                "polygon": [[0, 20], [50, 20], [50, 30], [0, 30]],
                "recognition_confidence": None,
            },
        ],
    }


def selection(**values):
    return {field: {"region_ids": values.get(field, [])} for field in FIELDS}


def test_adapter_retains_low_confidence_and_no_ground_truth():
    a = adapt(receipt(), 100, 100)
    assert a == adapt(receipt(), 100, 100)
    assert len(a["regions"]) == 2
    assert "SECRET_GT" not in json.dumps(a)
    assert a["mapping"]["R001"]["polygon"] == receipt()["predictions"][0]["polygon"]


def test_multiline_and_missing_confidence(tmp_path):
    a = adapt(receipt(), 100, 100)
    fields = validate(selection(seller_address=["R001", "R002"]), a)
    assert fields["seller_address"]["value_raw"] == "Địa chỉ <script>\nHà Nội"
    assert fields["seller_address"]["ocr_confidence"] is None
    assert fields["seller_name"]["status"] == "not_found"
    render_demo(
        [{"image_id": "a", "status": "ok", "fields": fields}],
        tmp_path,
        {"a": "image.jpg"},
    )
    text = (tmp_path / "demo.html").read_text(encoding="utf-8")
    assert "&lt;script&gt;" in text and "<script>" not in text


@pytest.mark.parametrize("ids", [["R099"], ["R001", "R001"], None, [1]])
def test_reject_bad_ids(ids):
    with pytest.raises(ValueError):
        validate(selection(seller_name=ids), adapt(receipt(), 100, 100))


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("90,996", 90996),
        ("1.300,000", 1300000),
        ("650,000\n650,000", None),
        ("12,50", None),
        ("Tiền 24.000 đ", 24000),
    ],
)
def test_amount(raw, expected):
    assert normalize("total_amount", raw)[0] == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Ngày: 09/08/2020 21:20", "2020-08-09T21:20:00"),
        ("02/06/2020", "2020-06-02"),
        ("31/02/2020", None),
        ("02/06/2020\n19:01", "2020-06-02T19:01:00"),
    ],
)
def test_datetime(raw, expected):
    assert normalize("transaction_datetime", raw)[0] == expected


def test_exclusions_and_partial():
    row = receipt()
    row["status"] = "partial"
    row["predictions"] += [
        {"text": "", "polygon": []},
        {"text": "x", "polygon": [[float("nan"), 0]] * 4},
    ]
    row["predictions"][0]["recognition_confidence"] = float("nan")
    a = adapt(row, 100, 100)
    assert len(a["excluded"]) == 2 and len(a["mapping"]) == 2
    assert a["mapping"]["R001"]["confidence"] is None
    assert (
        "partial_ocr"
        in validate(selection(seller_name=["R001"]), a)["seller_name"]["issues"]
    )


def test_context_and_truncation(tmp_path):
    class Client(QwenClient):
        def request(self, endpoint, payload=None):
            if endpoint == "/apply-template":
                return {"prompt": "text"}
            if endpoint == "/tokenize":
                return {"tokens": [1] * 10}
            return {
                "choices": [{"finish_reason": "length", "message": {"content": "{}"}}]
            }

    a = adapt(receipt(), 100, 100)
    with pytest.raises(ValueError, match="Context exceeded"):
        Client(context=20).extract(a, tmp_path)
    with pytest.raises(ValueError, match="Incomplete"):
        Client().extract(a, tmp_path)


def test_shared_evidence():
    fields = validate(
        selection(seller_name=["R001"], seller_address=["R001"]),
        adapt(receipt(), 100, 100),
    )
    assert fields["seller_name"]["status"] == "needs_review"
