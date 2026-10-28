from docucheck.data.splitting import assign_internal_splits, find_cross_split_duplicate_groups
import pytest


def test_split_is_deterministic_and_keeps_duplicate_groups_together():
    records = [
        {"image_id": "a", "image_group_id": "duplicate"},
        {"image_id": "b", "image_group_id": "duplicate"},
        {"image_id": "c", "image_group_id": "unique-c"},
        {"image_id": "d", "image_group_id": "unique-d"},
        {"image_id": "e", "image_group_id": "unique-e"},
    ]
    first = assign_internal_splits(records, seed=17, validation_fraction=0.4)
    second = assign_internal_splits(records, seed=17, validation_fraction=0.4)
    assert [item["split"] for item in first] == [item["split"] for item in second]
    assert first[0]["split"] == first[1]["split"]
    assert find_cross_split_duplicate_groups(first) == {}


def test_split_rejects_invalid_fraction():
    try:
        assign_internal_splits([], validation_fraction=1.0)
    except ValueError as error:
        assert "strictly between" in str(error)
    else:
        raise AssertionError("Expected invalid split fraction to fail")


@pytest.mark.parametrize("missing", [True, False])
def test_missing_checksum_uses_same_fallback_for_grouping_and_assignment(missing):
    rows = [{"image_id": str(i), **({} if missing else {"image_group_id": None})} for i in range(5)]
    result = assign_internal_splits(rows)
    assert len(result) == len(rows)
    assert sum(r["split"] == "internal_dev" for r in result) == 1
    assert all("split" not in r for r in rows)
    reverse = assign_internal_splits(list(reversed(rows)))
    assert {r["image_id"]: r["split"] for r in result} == {r["image_id"]: r["split"] for r in reverse}


def test_single_duplicate_group_stays_train():
    rows = [{"image_id": str(i), "image_group_id": "same"} for i in range(3)]
    assert {r["split"] for r in assign_internal_splits(rows)} == {"internal_train"}
    assert assign_internal_splits([]) == []


@pytest.mark.parametrize("fraction", [0, 1, -0.1, 1.1, float("nan"), float("inf")])
def test_rejects_all_invalid_fractions(fraction):
    with pytest.raises(ValueError, match="strictly between"):
        assign_internal_splits([], validation_fraction=fraction)
