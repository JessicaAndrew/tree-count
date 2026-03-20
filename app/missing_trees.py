""" Logic for detecting missing trees in an orchard. TODO"""

import logging
import numpy as np
from typing import List, Tuple, Optional
from shapely.geometry import Polygon, Point
from app.models import GpsCoordinate

logger = logging.getLogger(__name__)


class MissingTreesDetector:
    """ Detector for missing trees in an orchard. """

    @staticmethod
    def parse_polygon_string(polygon_str: str) -> Optional[Polygon]:
        """
        Parse polygon string in format "lng,lat lng,lat ..." into Shapely Polygon.

        Args:
            polygon_str: Polygon string from Aerobotics API

        Returns:
            Shapely Polygon object or None if parsing fails
        """
        if not polygon_str:
            return None

        try:
            coords = []
            # Split by space to get "lng,lat" pairs
            pairs = polygon_str.strip().split()
            for pair in pairs:
                lng, lat = pair.split(',')
                coords.append((float(lng), float(lat)))

            if len(coords) < 3:
                logger.warning("Polygon has fewer than 3 points, cannot create valid polygon")
                return None

            return Polygon(coords)
        except Exception as e:
            logger.error(f"Failed to parse polygon string: {e}")
            return None

    @staticmethod
    def infer_row_direction(detected_trees: List[Tuple[float, float]]) -> float:
        """
        Infer planting row direction using PCA on detected tree positions.

        Args:
            detected_trees: List of (lat, lng) tuples

        Returns:
            Angle in radians of row direction (0 = east-west, pi/2 = north-south)
        """
        if len(detected_trees) < 3:
            return 0.0

        try:
            trees = np.array(detected_trees)
            centered = trees - trees.mean(axis=0)
            cov = np.cov(centered.T)
            eigenvalues, eigenvectors = np.linalg.eig(cov)
            principal_component = eigenvectors[:, np.argmax(eigenvalues)]
            angle = np.arctan2(principal_component[1], principal_component[0])
            return angle
        except Exception as e:
            logger.warning(f"Failed to infer row direction: {e}, using default")
            return 0.0

    @staticmethod
    def detect_missing_trees(
        orchard_polygon: Optional[str],
        detected_trees: List[Tuple[float, float]],
        row_spacing: float = 0.00005,
        tree_spacing: float = 0.00005,
        threshold: float = 0.00003,
    ) -> List[GpsCoordinate]:
        """
        Detect missing trees based on orchard polygon and detected trees.

        Algorithm:
        1. Parse orchard polygon boundary
        2. Infer row direction from detected tree positions (PCA)
        3. Generate expected grid aligned with row direction inside polygon
        4. Find grid positions without nearby detected trees
        5. Return GPS coordinates of missing tree positions

        Args:
            orchard_polygon: Polygon string "lng,lat lng,lat ..." from API
            detected_trees: List of (lat, lng) tuples of detected trees
            row_spacing: Spacing between rows (in degrees, ~0.00005 = 5.5m)
            tree_spacing: Spacing between trees in a row (in degrees)
            threshold: Distance threshold to match grid point to detected tree

        Returns:
            List of GpsCoordinate objects for missing trees.
        """
        if not detected_trees:
            return []

        # Parse polygon from string format
        poly = MissingTreesDetector.parse_polygon_string(orchard_polygon)
        if not poly:
            logger.warning("Cannot parse orchard polygon, returning empty missing trees")
            return []

        # Get bounding box from polygon
        min_lng, min_lat, max_lng, max_lat = poly.bounds

        # Infer row direction from detected tree positions
        angle = MissingTreesDetector.infer_row_direction(detected_trees)

        # Generate expected tree grid inside polygon
        expected_positions = MissingTreesDetector._generate_grid_in_polygon(
            poly, min_lat, max_lat, min_lng, max_lng,
            row_spacing, tree_spacing, angle
        )

        if not expected_positions:
            logger.warning("No expected grid positions generated inside polygon")
            return []

        # Find missing trees
        missing_trees = []
        for exp_lat, exp_lng in expected_positions:
            found = False
            for det_lat, det_lng in detected_trees:
                distance = ((exp_lat - det_lat) ** 2 + (exp_lng - det_lng) ** 2) ** 0.5
                if distance < threshold:
                    found = True
                    break

            if not found:
                missing_trees.append(GpsCoordinate(lat=exp_lat, lng=exp_lng))

        logger.info(
            f"Detected {len(missing_trees)} missing trees out of {len(expected_positions)} expected positions"
        )
        return missing_trees

    @staticmethod
    def _generate_grid_in_polygon(
        polygon: Polygon,
        min_lat: float,
        max_lat: float,
        min_lng: float,
        max_lng: float,
        row_spacing: float,
        tree_spacing: float,
        angle: float,
    ) -> List[Tuple[float, float]]:
        """
        Generate grid of expected tree positions aligned with row direction inside polygon.

        Args:
            polygon: Shapely Polygon of orchard boundary
            min_lat: Min latitude of bounding box
            max_lat: Max latitude of bounding box
            min_lng: Min longitude of bounding box
            max_lng: Max longitude of bounding box
            row_spacing: Distance between rows
            tree_spacing: Distance between trees in row
            angle: Row direction angle in radians

        Returns:
            List of (lat, lng) tuples for expected tree positions inside polygon
        """
        grid = []

        # Create orthogonal grid for simplicity (EW/NS aligned)
        if abs(angle) < 0.2 or abs(angle - 3.14159) < 0.2:
            # East-West rows
            current_lat = min_lat
            while current_lat <= max_lat:
                current_lng = min_lng
                while current_lng <= max_lng:
                    point = Point(current_lng, current_lat)
                    if polygon.contains(point):
                        grid.append((round(current_lat, 6), round(current_lng, 6)))
                    current_lng += tree_spacing
                current_lat += row_spacing

        elif abs(angle - 1.5708) < 0.2 or abs(angle + 1.5708) < 0.2:
            # North-South rows
            current_lng = min_lng
            while current_lng <= max_lng:
                current_lat = min_lat
                while current_lat <= max_lat:
                    point = Point(current_lng, current_lat)
                    if polygon.contains(point):
                        grid.append((round(current_lat, 6), round(current_lng, 6)))
                    current_lat += tree_spacing
                current_lng += row_spacing
        else:
            # Rotated grid for arbitrary angle
            cos_a = np.cos(angle)
            sin_a = np.sin(angle)

            center_lat = (min_lat + max_lat) / 2
            center_lng = (min_lng + max_lng) / 2
            extent_lat = max_lat - min_lat
            extent_lng = max_lng - min_lng
            max_extent = max(extent_lat, extent_lng) / min(row_spacing, tree_spacing) + 10

            for i in range(-int(max_extent), int(max_extent)):
                for j in range(-int(max_extent), int(max_extent)):
                    lat = center_lat + (i * row_spacing * cos_a) + (j * tree_spacing * sin_a)
                    lng = center_lng + (-i * row_spacing * sin_a) + (j * tree_spacing * cos_a)
                    point = Point(lng, lat)
                    if polygon.contains(point):
                        grid.append((round(lat, 6), round(lng, 6)))

        return grid

