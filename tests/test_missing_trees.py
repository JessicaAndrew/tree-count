"""Unit tests for the missing trees detection logic. TODO"""

import pytest
from app.missing_trees import MissingTreesDetector
from app.models import GpsCoordinate


class TestMissingTreesDetector:
    """Test cases for MissingTreesDetector."""

    def test_detect_missing_trees_empty_detected_trees(self):
        """Test detection with no detected trees."""
        bounds = (-33.0, -32.0, 18.0, 19.0)
        detected_trees = []

        result = MissingTreesDetector.detect_missing_trees(
            orchard_bounds=bounds,
            detected_trees=detected_trees,
        )

        assert result == []

    def test_detect_missing_trees_with_detected_trees(self):
        """Test detection with some detected trees."""
        # Small orchard bounds
        bounds = (-33.0, -33.001, 18.0, 18.001)

        # One detected tree at the center
        detected_trees = [(-33.0005, 18.0005)]

        result = MissingTreesDetector.detect_missing_trees(
            orchard_bounds=bounds,
            detected_trees=detected_trees,
            row_spacing=0.0005,
            tree_spacing=0.0005,
            threshold=0.0003,
        )

        # Should detect missing trees (excluding the detected one)
        assert isinstance(result, list)
        assert all(isinstance(tree, GpsCoordinate) for tree in result)

    def test_detect_missing_trees_all_present(self):
        """Test when all expected trees are detected."""
        # Create a small grid
        bounds = (-33.0, -33.0005, 18.0, 18.0005)

        # Trees at grid points
        detected_trees = [
            (-33.0, 18.0),
            (-33.0005, 18.0),
            (-33.0, 18.0005),
            (-33.0005, 18.0005),
        ]

        result = MissingTreesDetector.detect_missing_trees(
            orchard_bounds=bounds,
            detected_trees=detected_trees,
            row_spacing=0.0005,
            tree_spacing=0.0005,
            threshold=0.0001,
        )

        # Should detect zero or very few missing trees
        assert len(result) <= 1  # Allow for rounding

    def test_generate_grid(self):
        """Test grid generation."""
        min_lat, max_lat = -33.0, -33.001
        min_lng, max_lng = 18.0, 18.001

        grid = MissingTreesDetector._generate_grid(
            min_lat=min_lat,
            max_lat=max_lat,
            min_lng=min_lng,
            max_lng=max_lng,
            row_spacing=0.0005,
            tree_spacing=0.0005,
        )

        assert isinstance(grid, list)
        assert len(grid) > 0
        assert all(isinstance(point, tuple) and len(point) == 2 for point in grid)

        # Check bounds
        lats = [lat for lat, lng in grid]
        lngs = [lng for lat, lng in grid]
        assert min(lats) >= min_lat
        assert max(lats) <= max_lat
        assert min(lngs) >= min_lng
        assert max(lngs) <= max_lng

    def test_grid_point_coverage(self):
        """Test that grid covers the full bounds."""
        min_lat, max_lat = -33.0, -33.002
        min_lng, max_lng = 18.0, 18.002

        grid = MissingTreesDetector._generate_grid(
            min_lat=min_lat,
            max_lat=max_lat,
            min_lng=min_lng,
            max_lng=max_lng,
            row_spacing=0.001,
            tree_spacing=0.001,
        )

        # With 0.001 spacing, we should have at least 3x3 = 9 points
        assert len(grid) >= 9

    def test_gps_coordinate_model(self):
        """Test GPS coordinate model."""
        coord = GpsCoordinate(lat=-33.33, lng=18.88)

        assert coord.lat == -33.33
        assert coord.lng == 18.88


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
