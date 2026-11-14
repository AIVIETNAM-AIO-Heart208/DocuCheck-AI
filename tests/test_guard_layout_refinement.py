"""Opt-in geometry, exact evidence and advisory guard contracts (not yet run)."""

from copy import deepcopy
import json
from math import cos, radians, sin

import pytest

from docucheck.extraction.qwen import QwenClient, adapt, normalize
from docucheck.extraction.refined import advisory, layout, resolve_text, role_hypotheses, text_registry, decode_text_ids


def receipt(entries, angle=0, scale=1):
    c, s = cos(radians(angle)), sin(radians(angle))
    predictions = []
    for i, (text, x, y, width) in enumerate(entries):
        points = [[scale*(px*c-py*s+200), scale*(px*s+py*c+200)]
                  for px, py in [(x,y), (x+width,y), (x+width,y+16), (x,y+16)]]
        predictions.append({"text": text, "candidate_id": str(i), "polygon": points,
                            "recognition_confidence": .2})
    return adapt({"image_id": "fixture", "status": "ok", "predictions": predictions}, 2400, 2400)


def selection(a):
    return [{"region_id": k, "start": 0, "end": len(v["text"]), "joiner": " "}
            for k, v in a["mapping"].items()]


@pytest.mark.parametrize("angle", [-18, 0, 18])
@pytest.mark.parametrize("scale", [.5, 1, 2])
def test_horizontal_name_survives_tilt_scale_and_permutation(angle, scale):
    a = receipt([("THỨC",0,0,55), ("COFFEE",65,0,90)], angle, scale)
    untouched = deepcopy(a)
    chosen = list(reversed(selection(a)))
    g = layout(a["mapping"])
    assert any(len(v["region_ids"]) == 2 for v in g["alternatives"])
    result = resolve_text("seller_name", chosen, a, g, normalize)
    assert result["value_normalized"] == "THỨC COFFEE"
    assert a == untouched


def test_columns_split_but_repeated_words_are_preserved():
    a = receipt([("COCO COCO",0,0,100), ("22 Road",300,0,100)])
    g = layout(a["mapping"])
    assert len(g["lines"]) == 2
    result = resolve_text("seller_name", selection(a)[:1], a, g, normalize)
    assert result["value_normalized"] == "COCO COCO"


def test_name_address_can_share_region_with_disjoint_offsets():
    a = receipt([("SHOP 22 Road Tel:123",0,0,200)])
    key = next(iter(a["mapping"]))
    g = layout(a["mapping"])
    def part(start, end):
        return [{"region_id": key, "start": start, "end": end, "joiner": " "}]
    assert resolve_text("seller_name", part(0,4), a,g,normalize)["value_normalized"] == "SHOP"
    assert resolve_text("seller_address", part(5,12), a,g,normalize)["value_normalized"] == "22 Road"
    with pytest.raises(ValueError):
        resolve_text("seller_address", part(0,999), a,g,normalize)
    with pytest.raises(ValueError):
        resolve_text("seller_address", part(0,4)*2, a,g,normalize)


def test_empty_join_is_reviewed_without_dictionary_correction():
    a = receipt([("Vin",0,0,30), ("Commerce",32,0,95)])
    chosen = selection(a)
    chosen[1]["joiner"] = ""
    value = resolve_text("seller_name", chosen,a,layout(a["mapping"]),normalize)
    assert value["value_normalized"] == "VinCommerce"
    assert "uncertain_word_boundary" in value["issues"]


@pytest.mark.parametrize("label,expected", [("SUBTOTAL", "subtotal"), ("TOTAL", "invoice_total"),
    ("DISCOUNT", "discount"), ("CHANGE", "change"), ("CASH", "tendered_amount"),
    ("Tổng cộng", "invoice_total"), ("Card", "payment_component")])
def test_roles_are_hypotheses(label, expected):
    assert expected in role_hypotheses(label)
    assert "invoice_total" not in role_hypotheses("SUBTOTAL")


def test_conflicting_roles_observable_and_guard_never_replaces():
    assert {"discount", "invoice_total"} <= set(role_hypotheses("TOTAL; DISCOUNT"))
    groups = {"total_amount": {"M1": {"label_evidence": [{"text": "unfamiliar label"}]},
                               "M2": {"label_evidence": [{"text": "TOTAL"}]}}}
    for chosen in (None, "M1", "M2"):
        decision = advisory({"total_amount": chosen}, groups)
        assert decision["final_candidate_id"] == chosen


def test_default_mode_and_invalid_mode():
    assert QwenClient().extraction_mode == "baseline"
    with pytest.raises(ValueError):
        QwenClient(extraction_mode="other")


def test_refined_client_isolates_bad_name_and_preserves_money(tmp_path):
    a = receipt([("STORE",0,0,80), ("TOTAL 35,000",0,30,180)])
    name_key = next(k for k,v in a["mapping"].items() if v["text"] == "STORE")
    chosen = {"seller_name": [{"region_id":name_key,"start":0,"end":999,"joiner":" "}],
              "seller_address": [], "total_amount":"M001", "transaction_datetime":None}
    class Client(QwenClient):
        def request(self, endpoint, payload=None):
            if endpoint == "/apply-template":
                return {"prompt":"fixture"}
            if endpoint == "/tokenize":
                return {"tokens":[1]}
            return {"choices":[{"finish_reason":"stop", "message":{"content":json.dumps(chosen)}}]}
    row = Client(extraction_mode="refined").extract(a,tmp_path)
    assert row["fields"]["seller_name"]["value_normalized"] is None
    assert row["fields"]["total_amount"]["value_normalized"] == 35000
    assert row["raw_model_selection"] == chosen
    assert row["final_selection"]["seller_name"] == []
    assert row["final_selection"]["total_amount"] == chosen["total_amount"]
    assert (tmp_path / "coverage/fixture.json").exists()
    request = json.loads((tmp_path / "requests/fixture.json").read_text(encoding="utf-8"))
    body = json.loads(request["messages"][1]["content"])
    assert {r["id"] for r in body["regions"]} == set(a["mapping"])
    assert "text_alternatives" not in body  # Recoverable from lines/blocks, stored in ledger.
    assert all("bbox" not in line for line in body["lines"])
    assert all(isinstance(label, dict) for candidate in body["candidates"]["total_amount"]
               for label in candidate["labels"])


def test_context_failure_never_calls_completion(tmp_path):
    a = receipt([("STORE",0,0,80)])
    class Client(QwenClient):
        def request(self, endpoint, payload=None):
            if endpoint == "/apply-template":
                return {"prompt":"fixture"}
            assert endpoint == "/tokenize"
            return {"tokens":[1]*100}
    with pytest.raises(ValueError, match="Context exceeded"):
        Client(context=100, extraction_mode="refined").extract(a,tmp_path)


def test_bbox_fallback_and_missing_polygon_never_mix_units():
    a = receipt([("12",0,0,20), ("Road",25,0,60)])
    a["mapping"][next(iter(a["mapping"]))].pop("polygon")
    g = layout(a["mapping"])
    assert g["coordinate_source"] == "bbox"
    assert resolve_text("seller_address", selection(a),a,g,normalize)["value_normalized"] == "12 Road"


def test_multiline_block_and_budget_keep_original_evidence():
    a = receipt([("12 Road",0,0,100),("District",0,25,100),("City",0,50,100)])
    untouched = deepcopy(a)
    g = layout(a["mapping"],max_alternatives=1)
    assert g["omitted"]
    value = resolve_text("seller_address",selection(a),a,g,normalize)
    assert value["value_normalized"] == "12 Road District City"
    assert a == untouched


def test_duplicate_ocr_is_flagged_not_deduplicated():
    a = receipt([("COCO",0,0,100),("COCO",2,0,100)])
    g = layout(a["mapping"])
    assert g["overlap_hypotheses"]
    value = resolve_text("seller_name",selection(a),a,g,normalize)
    assert len(value["value_spans"]) == 2
    assert "selected_overlapping_ocr_hypotheses" in value["issues"]


@pytest.mark.parametrize("label", ["SUBTOTAL 20", "SUB TOTAL: 20"])
def test_subtotal_does_not_gain_generic_total_role(label):
    assert "invoice_total" not in role_hypotheses(label)


@pytest.mark.parametrize("label", ["CASH + CARD", "Đặt cọc", "TOTAL; CHANGE", "GROSS TOTAL", "VAT"])
def test_semantic_warnings_preserve_model_selection(label):
    groups = {"total_amount":{"M1":{"label_evidence":[{"text":label}]}}}
    result = advisory({"total_amount":"M1"},groups)
    assert result["final_candidate_id"] == "M1"
    assert result["issues"]


def test_model_cannot_supply_bbox_as_character_offsets():
    a = receipt([("Vincommerce",0,0,154)])
    registry = text_registry(a["mapping"])
    key = next(iter(a["mapping"]))
    with pytest.raises(ValueError, match="text ID"):
        decode_text_ids([{"region_id":key,"start":198,"end":352,"joiner":" "}],registry)
    assert decode_text_ids([key],registry)[0]["end"] == len("Vincommerce")


def test_text_parts_remain_exact_and_whole_region_available():
    a = receipt([("SHOP | Address: 22 Road Tel:123",0,0,200)])
    registry = text_registry(a["mapping"])
    key = next(iter(a["mapping"]))
    assert key in registry
    assert len(registry) > 1
    for span in registry.values():
        assert span["text"] == a["mapping"][span["region_id"]]["text"][span["start"]:span["end"]]
    parts = [v["text"] for k,v in registry.items() if k != key]
    assert "SHOP" in parts
    assert "22 Road" in parts
    assert "|" not in parts
    assert "Address:" not in parts


def test_refined_id_schema_and_successful_full_region_selection(tmp_path):
    a = receipt([("STORE",0,0,80),("22 Road",0,25,100),("TOTAL 35,000",0,60,180)])
    by_text = {r["text"]:key for key,r in a["mapping"].items()}
    selected = {"seller_name":[by_text["STORE"]],"seller_address":[by_text["22 Road"]],
                "total_amount":None,"transaction_datetime":None}
    class Client(QwenClient):
        def request(self, endpoint, payload=None):
            if endpoint == "/apply-template":
                return {"prompt":"fixture"}
            if endpoint == "/tokenize":
                return {"tokens":[1]}
            schema = payload["response_format"]["json_schema"]["schema"]
            assert schema["properties"]["seller_name"]["items"]["enum"]
            data = json.loads(payload["messages"][1]["content"])
            money = data["candidates"]["total_amount"]
            totals = [candidate for candidate in money
                      if candidate["text"] == "35,000"
                      and candidate["regions"] == [by_text["TOTAL 35,000"]]]
            assert len(totals) == 1
            total = totals[0]
            assert "spans" not in total
            assert total["id"] in schema["properties"]["total_amount"]["enum"]
            # The number in the address is a separate candidate, not the total.
            assert any(candidate["text"] == "22"
                       and candidate["regions"] == [by_text["22 Road"]]
                       and candidate["id"] != total["id"] for candidate in money)
            selected["total_amount"] = total["id"]
            assert "start" not in json.dumps(schema["properties"]["seller_name"])
            return {"choices":[{"finish_reason":"stop","message":{"content":json.dumps(selected)}}]}
    result = Client(extraction_mode="refined").extract(a,tmp_path)
    assert result["fields"]["seller_name"]["value_normalized"] == "STORE"
    assert result["fields"]["seller_address"]["value_normalized"] == "22 Road"
    assert result["fields"]["total_amount"]["value_normalized"] == 35000
    assert result["fields"]["total_amount"]["evidence_region_ids"] == [by_text["TOTAL 35,000"]]
    assert result["raw_model_selection"]["total_amount"] == selected["total_amount"]
    assert "model_abstained" in result["fields"]["transaction_datetime"]["issues"]
