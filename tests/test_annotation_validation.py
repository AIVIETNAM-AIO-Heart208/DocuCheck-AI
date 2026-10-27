from docucheck.data.validation import validate_polygon


def test_accepts_valid_polygon_inside_image():
    assert validate_polygon([[1, 1], [9, 1], [9, 8], [1, 8]], 10, 10) == []


def test_reports_invalid_polygon_geometry():
    assert validate_polygon([[1, 1], [2, 2]], 10, 10) == ["missing_or_too_few_vertices"]
    assert "zero_area" in validate_polygon([[1, 1], [2, 2], [3, 3]], 10, 10)
    assert "out_of_image_bounds" in validate_polygon([[-1, 1], [2, 1], [2, 3]], 10, 10)
