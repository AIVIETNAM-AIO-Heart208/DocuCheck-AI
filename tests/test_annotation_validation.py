from docucheck.data.validation import validate_polygon
from docucheck.data.validation import validate_manifest
import pytest


def test_accepts_valid_polygon_inside_image():
    assert validate_polygon([[1, 1], [9, 1], [9, 8], [1, 8]], 10, 10) == []


def test_reports_invalid_polygon_geometry():
    assert validate_polygon([[1, 1], [2, 2]], 10, 10) == ["missing_or_too_few_vertices"]
    assert "zero_area" in validate_polygon([[1, 1], [2, 2], [3, 3]], 10, 10)
    assert "out_of_image_bounds" in validate_polygon([[-1, 1], [2, 1], [2, 3]], 10, 10)


def test_nonzero_area_self_intersection_and_malformed_vertices():
    assert "self_intersection" in validate_polygon([[0, 0], [6, 5], [0, 4], [4, 0]], 10, 10)
    assert validate_polygon([[0, 0, 3], [1, 0], [1, 1]], 10, 10) == ["malformed_vertices"]
    assert validate_polygon([[{}, 0], [1, 0], [1, 1]], 10, 10) == ["malformed_vertices"]
    assert "non_finite_coordinates" in validate_polygon([[float("nan"), 0], [1, 0], [1, 1]], 10, 10)
    assert "image_dimensions_unavailable" in validate_polygon([[0, 0], [1, 0], [1, 1]], 0, 0)


@pytest.mark.parametrize("path", ["C:/private/a.jpg", "C:receipt.jpg", "../a.jpg", "x/../a.jpg", "\\\\host\\share\\a.jpg", "/a.jpg", ""])
def test_cross_platform_unsafe_manifest_paths(path):
    report = validate_manifest([{"image_id": "id", "image_path": path}])
    assert report["issue_counts"]["invalid_or_absolute_image_paths"] == 1


def test_invalid_duplicate_ids_and_leakage_are_detected():
    records = [{"image_id": "a", "image_path": "a.jpg", "image_group_id": "same", "split": split}
               for split in ("internal_train", "internal_dev")]
    records.append({"image_id": None, "image_path": "b.jpg", "regions": None})
    report = validate_manifest(records)
    for key in ("duplicate_image_ids", "invalid_image_ids", "cross_split_exact_duplicate_groups", "invalid_region_arrays"):
        assert report["issue_counts"][key] == 1
