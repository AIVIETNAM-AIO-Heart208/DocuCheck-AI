"""Pure synthetic request contracts; no OCR/model required."""
from copy import deepcopy
import json

from docucheck.extraction.context_budget import fit_request, table_data


def data():
    return {"regions": [{"id":"R1", "text":"TOTAL 35 000", "bbox":[0,0,50,10]}],
            "optional_text_parts":[], "lines":[], "blocks":[], "ocr_merge_hints":[],
            "candidates":{"total_amount":[{"id":"M1", "regions":["R1"],
                "text":"35 000", "labels":[{"region_id":"R1", "text":"TOTAL"}],
                "label_alternatives":[], "role_hypotheses":["invoice_total"]}]}}


def test_tables_preserve_substrings_ids_and_scoped_labels():
    original = data()
    untouched = deepcopy(original)
    result = table_data(original)
    assert original == untouched
    assert result["regions"]["rows"][0] == ["R1", "TOTAL 35 000", [0,0,50,10]]
    assert result["candidates"]["total_amount"]["rows"][0][:4] == ["M1", ["R1"], "35 000", ["R1"]]
    assert result["scoped_label_text"] == [["total_amount", "M1", "R1", "TOTAL"]]


class FakeClient:
    context = 8192

    def __init__(self, counts):
        self.counts = iter(counts)
        self.calls = []

    def request(self, endpoint, payload):
        self.calls.append(endpoint)
        if endpoint == "/apply-template":
            return {"prompt":"synthetic"}
        assert endpoint == "/tokenize"  # Never calls generation.
        return {"tokens":[0]*next(self.counts)}


def payload():
    return {"messages":[{"role":"system","content":"instructions"},
                        {"role":"user","content":"original"}],"max_tokens":512}


def test_fitting_request_is_unchanged():
    request = payload()
    before = deepcopy(request)
    tokens, attempts = fit_request(FakeClient([2000]), request, data())
    assert request == before
    assert len(attempts) == 1


def test_overflow_uses_tables_without_dropping_evidence():
    request = payload()
    client = FakeClient([8433, 6000])
    tokens, attempts = fit_request(client, request, data())
    assert len(tokens) == 6000
    assert len(client.calls) == 4
    assert json.loads(request["messages"][1]["content"]) == table_data(data())
    assert attempts[-1]["version"] == "tables_v1"


def test_still_oversized_stops_after_two_preflights():
    client = FakeClient([9000, 8500])
    tokens, attempts = fit_request(client, payload(), data())
    assert len(tokens) + 512 > client.context
    assert len(attempts) == 2
