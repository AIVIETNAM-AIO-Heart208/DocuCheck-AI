from docucheck.data.splitting import assign_internal_splits, find_cross_split_duplicate_groups


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
