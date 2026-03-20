"""Unit tests for the missing trees detection logic. TODO"""

import pytest
from app.missing_trees import MissingTreesDetector
from app.models import GpsCoordinate


class TestMissingTreesDetector:
    """Test cases for MissingTreesDetector."""

    def test_parse_polygon_string_valid(self):
        """Test valid polygon parsing."""
        polygon_str = "18.0,-33.0 18.002,-33.0 18.002,-33.002 18.0,-33.002 18.0,-33.0"

        polygon = MissingTreesDetector.parse_polygon_string(polygon_str)

        assert polygon is not None
        assert polygon.is_valid

    def test_parse_polygon_string_invalid(self):
        """Test invalid polygon parsing returns None."""
        polygon_str = "18.0,-33.0 18.001,-33.001"

        polygon = MissingTreesDetector.parse_polygon_string(polygon_str)

        assert polygon is None

    def test_detect_missing_trees_empty_detected_trees(self):
        """Test detection with no detected trees."""
        polygon = "18.0,-33.0 18.002,-33.0 18.002,-33.002 18.0,-33.002 18.0,-33.0"
        detected_trees = []

        result = MissingTreesDetector.detect_missing_trees(
            orchard_polygon=polygon,
            detected_trees=detected_trees,
        )

        assert result == []

    def test_detect_missing_trees_invalid_polygon(self):
        """Test invalid polygon returns empty result."""
        detected_trees = [(-33.0005, 18.0005)]

        result = MissingTreesDetector.detect_missing_trees(
            orchard_polygon="invalid",
            detected_trees=detected_trees,
        )

        assert result == []

    def test_detect_missing_trees_detects_center_gap(self):
        """Test detector can find a missing center tree in a near-regular grid."""
        polygon = "18.0,-33.0 18.0012,-33.0 18.0012,-33.0012 18.0,-33.0012 18.0,-33.0"

        detected_trees = [
            (-33.0, 18.0),
            (-33.0, 18.0005),
            (-33.0, 18.0010),
            (-33.0005, 18.0),
            (-33.0005, 18.0010),
            (-33.0010, 18.0),
            (-33.0010, 18.0005),
            (-33.0010, 18.0010),
        ]

        result = MissingTreesDetector.detect_missing_trees(
            orchard_polygon=polygon,
            detected_trees=detected_trees,
            row_spacing=0.0005,
            tree_spacing=0.0005,
            threshold=0.00015,
        )

        assert isinstance(result, list)
        assert all(isinstance(tree, GpsCoordinate) for tree in result)
        assert any(abs(tree.lat - (-33.0005)) < 0.0002 and abs(tree.lng - 18.0005) < 0.0002 for tree in result)

    def test_metric_projection_round_trip(self):
        """Test metric conversion round-trip preserves coordinates closely."""
        import numpy as np

        points = np.array([
            [-33.0, 18.0],
            [-33.0005, 18.0005],
            [-33.001, 18.001],
        ], dtype=float)

        metric_points, mean_lat_rad = MissingTreesDetector._to_metric_points(points)
        recovered = [MissingTreesDetector._from_metric_point(point, mean_lat_rad) for point in metric_points]

        assert len(recovered) == len(points)
        for (lat_expected, lng_expected), (lat_actual, lng_actual) in zip(points, recovered):
            assert abs(lat_expected - lat_actual) < 1e-9
            assert abs(lng_expected - lng_actual) < 1e-9

    def test_gps_coordinate_model(self):
        """Test GPS coordinate model."""
        coord = GpsCoordinate(lat=-33.33, lng=18.88)

        assert coord.lat == -33.33
        assert coord.lng == 18.88


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
