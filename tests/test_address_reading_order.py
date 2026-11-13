"""Address layout invariants and regression for fragmented, tilted OCR regions."""

from copy import deepcopy
from itertools import permutations
from math import cos, radians, sin
from random import Random

import pytest

from docucheck.extraction.candidates import build, resolve
from docucheck.extraction.qwen import FIELDS, QwenClient, adapt, normalize, validate
from docucheck.extraction.reading_order import order_regions


def adapted_regions(entries):
    return adapt(
        {
            "image_id": "layout-test",
            "status": "ok",
            "predictions": [
                {
                    "candidate_id": str(i),
                    "text": text,
                    "polygon": points,
                    "recognition_confidence": 0.7,
                }
                for i, (text, points) in enumerate(entries)
            ],
        },
        2400,
        2400,
    )


def rotated_box(x, y, width, height=20, angle=0, scale=1):
    c, s = cos(radians(angle)), sin(radians(angle))
    return [
        [scale * (px * c - py * s + 600), scale * (px * s + py * c + 400)]
        for px, py in [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]
    ]


def selected(ids):
    return {field: ids if field == "seller_address" else None for field in FIELDS}


def by_text(a):
    return {v["text"]: key for key, v in a["mapping"].items()}


def milano():
    # The source OCR sorts min-y first: the actual right-hand fragments arrive first.
    return adapted_regions(
        [
            ("Vấp, TP.HCM", [[290, 320], [396, 311], [398, 337], [293, 346]]),
            ("Q.Gò", [[249, 324], [295, 320], [297, 344], [251, 347]]),
            ("Trâm,", [[160, 323], [211, 323], [211, 348], [160, 348]]),
            ("Cây", [[126, 324], [162, 324], [162, 348], [126, 348]]),
            ("186", [[94, 325], [128, 325], [128, 346], [94, 346]]),
            ("P.11,", [[208, 325], [254, 325], [254, 347], [208, 347]]),
        ]
    )


def test_milano_preserves_all_source_spans_and_model_selection():
    a = milano()
    ids = list(a["mapping"])
    selection = selected(ids)
    original_a, original_selection = deepcopy(a), deepcopy(selection)
    result = resolve(selection, build(a), a, normalize)["seller_address"]
    assert result["value_raw"] == "186 Cây Trâm, P.11, Q.Gò Vấp, TP.HCM"
    assert result["value_normalized"] == result["display_value"] == result["value_raw"]
    assert set(result["evidence_region_ids"]) == set(ids)
    assert result["reading_order"]["reordered"]
    assert len(result["reading_order"]["line_region_ids"]) == 1
    assert result["status"] == "ok"
    assert a == original_a and selection == original_selection
    for span in result["value_spans"]:
        assert (
            span["text"]
            == a["mapping"][span["region_id"]]["text"][span["start"] : span["end"]]
        )


@pytest.mark.parametrize("angle", [-18, -8, 0, 8, 18])
@pytest.mark.parametrize("scale", [0.5, 1, 2])
def test_multiline_order_survives_rotation_scale_and_input_permutations(angle, scale):
    # Separate rows have strongly overlapping original y ranges when tilted.
    entries = [
        ("12", rotated_box(0, 0, 25, angle=angle, scale=scale)),
        ("Road", rotated_box(30, 0, 80, angle=angle, scale=scale)),
        ("District", rotated_box(-20, 35, 100, angle=angle, scale=scale)),
        ("City", rotated_box(85, 35, 60, angle=angle, scale=scale)),
    ]
    for permuted in permutations(entries):
        a = adapted_regions(permuted)
        ids = list(reversed(a["mapping"]))
        value = resolve(selected(ids), build(a), a, normalize)["seller_address"]
        assert value["value_raw"] == "12 Road\nDistrict City"
        assert value["value_normalized"] == "12 Road District City"
        assert value["status"] == "ok"
        assert len(value["reading_order"]["line_region_ids"]) == 2


def test_order_is_independent_of_selected_id_order():
    a = milano()
    ids = list(a["mapping"])
    reference = order_regions(a["mapping"], ids)
    for permuted in permutations(ids):
        assert order_regions(a["mapping"], list(permuted)) == reference


def test_polygon_vertex_start_and_winding_do_not_change_order():
    a = adapted_regions(
        [
            ("left", rotated_box(0, 0, 60, angle=-15)),
            ("right", rotated_box(70, 0, 90, angle=-15)),
            ("next", rotated_box(0, 35, 90, angle=-15)),
        ]
    )
    ids = list(a["mapping"])
    reference = order_regions(a["mapping"], ids)
    rng = Random(42)
    for _ in range(20):
        for region in a["mapping"].values():
            points = region["polygon"]
            offset = rng.randrange(4)
            points = points[offset:] + points[:offset]
            region["polygon"] = points if rng.randrange(2) else list(reversed(points))
        assert order_regions(a["mapping"], ids) == reference


def test_rows_do_not_merge_through_a_staircase_of_fragments():
    a = adapted_regions(
        [
            ("a", rotated_box(0, 0, 30)),
            ("b", rotated_box(35, 9, 30)),
            ("c", rotated_box(70, 18, 30)),
        ]
    )
    assert len(order_regions(a["mapping"], list(a["mapping"])).lines) == 2


def test_singleton_empty_and_repeated_words_remain_exact():
    a = adapted_regions(
        [
            ("COCO COCO", rotated_box(0, 0, 90)),
            ("COCO", rotated_box(100, 0, 50)),
            ("UNSELECTED", rotated_box(0, 40, 90)),
        ]
    )
    ids = by_text(a)
    groups = build(a)
    for chosen, expected in [
        ([], None),
        ([ids["COCO COCO"]], "COCO COCO"),
        ([ids["COCO"], ids["COCO COCO"]], "COCO COCO COCO"),
    ]:
        value = resolve(selected(chosen), groups, a, normalize)["seller_address"]
        assert value["value_normalized"] == expected
        assert set(value["evidence_region_ids"]) == set(chosen)


def test_bbox_fallback_uses_one_coordinate_system():
    a = milano()
    a["mapping"][next(iter(a["mapping"]))].pop("polygon")
    ordered = order_regions(a["mapping"], list(a["mapping"]))
    assert ordered.coordinate_source == "bbox"
    assert ordered.text(a["mapping"]) == "186 Cây Trâm, P.11, Q.Gò Vấp, TP.HCM"


def test_overlapping_selected_regions_are_retained_and_flagged():
    a = adapted_regions(
        [
            ("first", rotated_box(0, 0, 100)),
            ("duplicate crop", rotated_box(5, 0, 100)),
        ]
    )
    ids = list(a["mapping"])
    value = resolve(selected(ids), build(a), a, normalize)["seller_address"]
    assert value["status"] == "needs_review"
    assert "ambiguous_address_reading_order" in value["issues"]
    assert len(value["value_spans"]) == 2


@pytest.mark.parametrize("ids", [["R001", "R001"], ["missing"], None, [1]])
def test_invalid_address_selection_is_still_rejected(ids):
    a = milano()
    with pytest.raises(ValueError, match="Invalid address IDs"):
        resolve(selected(ids), build(a), a, normalize)


def test_legacy_resolver_uses_the_same_order():
    a = milano()
    choice = {
        field: {"region_ids": list(a["mapping"]) if field == "seller_address" else []}
        for field in FIELDS
    }
    value = validate(choice, a)["seller_address"]
    assert value["value_raw"] == "186 Cây Trâm, P.11, Q.Gò Vấp, TP.HCM"


def test_client_retains_raw_response_and_only_reorders_address(tmp_path):
    import json

    a = milano()
    choice = selected(list(a["mapping"]))

    class Client(QwenClient):
        def request(self, endpoint, payload=None):
            if endpoint == "/apply-template":
                return {"prompt": "test"}
            if endpoint == "/tokenize":
                return {"tokens": [1]}
            return {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(choice),
                        },
                    }
                ]
            }

    result = Client().extract(a, tmp_path)
    assert result["raw_model_selection"] == choice
    assert result["final_selection"]["seller_address"] == choice["seller_address"]
    assert (
        result["fields"]["seller_address"]["value_normalized"]
        == "186 Cây Trâm, P.11, Q.Gò Vấp, TP.HCM"
    )
    assert (
        result["raw_fields"]["seller_address"]["reading_order"]["selected_region_ids"]
        == choice["seller_address"]
    )
