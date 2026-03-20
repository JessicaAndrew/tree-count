""" Logic for detecting missing trees in an orchard. TODO"""

import logging
import numpy as np
from typing import List, Tuple, Optional
from shapely.geometry import Polygon, Point
from app.models import GpsCoordinate

logger = logging.getLogger(__name__)


class MissingTreesDetector:
    """ Detector for missing trees in an orchard. """

    METERS_PER_DEG_LAT = 111320.0

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
    def infer_row_direction_from_polygon(polygon: Polygon) -> float:
        """
        Infer the orchard row direction from the longest edge of the boundary polygon.
        Rows are planted parallel to the longest boundary edge.

        Args:
            polygon: Shapely Polygon of the orchard boundary (coords in lng, lat)

        Returns:
            Angle in radians of the row direction in (lat, lng) space
        """
        coords = list(polygon.exterior.coords)
        best_angle = 0.0
        longest = 0.0

        for i in range(len(coords) - 1):
            lng1, lat1 = coords[i]
            lng2, lat2 = coords[i + 1]
            # Edge length (approximate, degrees)
            dlng = lng2 - lng1
            dlat = lat2 - lat1
            length = np.sqrt(dlat ** 2 + dlng ** 2)
            if length > longest:
                longest = length
                # Angle in (lat, lng) space: atan2(dlat, dlng)
                best_angle = np.arctan2(dlat, dlng)

        return best_angle

    @staticmethod
    def infer_row_direction(detected_trees: List[Tuple[float, float]]) -> float:
        """
        Fallback: infer row direction using PCA on detected tree positions.
        Prefer infer_row_direction_from_polygon when polygon is available.
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
        row_spacing: Optional[float] = None,
        tree_spacing: Optional[float] = None,
        threshold: Optional[float] = None,
    ) -> List[GpsCoordinate]:
        """
        Detect missing trees based on orchard polygon and detected trees.

        Algorithm:
        1. Parse orchard polygon boundary
        2. Infer row direction from detected tree positions (PCA)
        3. Normalize all detected trees to grid coordinates
        4. Find actual grid cell indices (round to nearest integer)
        5. Find empty grid cells adjacent to occupied cells
        6. Return GPS coordinates of missing tree positions

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

        tree_array = np.array(detected_trees, dtype=float)
        metric_points, mean_lat_rad = MissingTreesDetector._to_metric_points(tree_array)

        seed_angle = MissingTreesDetector._infer_row_direction_from_polygon_metric(poly, mean_lat_rad)
        row_angle = MissingTreesDetector._refine_row_angle_from_neighbors(metric_points, seed_angle)
        col_angle = row_angle + (np.pi / 2.0)

        axis_row = np.array([np.sin(row_angle), np.cos(row_angle)])
        axis_col = np.array([np.sin(col_angle), np.cos(col_angle)])

        inferred_row_spacing_m, inferred_tree_spacing_m = MissingTreesDetector._estimate_metric_spacings(
            metric_points,
            axis_row,
            axis_col,
        )

        row_spacing_m = row_spacing * MissingTreesDetector.METERS_PER_DEG_LAT if row_spacing else inferred_row_spacing_m
        tree_spacing_m = tree_spacing * MissingTreesDetector.METERS_PER_DEG_LAT if tree_spacing else inferred_tree_spacing_m
        base_spacing_m = float(min(row_spacing_m, tree_spacing_m))
        threshold_m = threshold * MissingTreesDetector.METERS_PER_DEG_LAT if threshold else (base_spacing_m * 0.30)

        centroid_m = metric_points.mean(axis=0)
        grid_positions_set: set[tuple[int, int]] = set()

        for point_m in metric_points:
            relative = point_m - centroid_m
            row_idx = np.dot(relative, axis_row) / row_spacing_m
            col_idx = np.dot(relative, axis_col) / tree_spacing_m

            row_grid = int(np.round(row_idx))
            col_grid = int(np.round(col_idx))
            grid_positions_set.add((row_grid, col_grid))

        # Find bounding box of grid cells
        if not grid_positions_set:
            return []
        
        rows = [r for r, c in grid_positions_set]
        cols = [c for r, c in grid_positions_set]
        min_row, max_row = min(rows), max(rows)
        min_col, max_col = min(cols), max(cols)
        
        # Check all candidate cells in the snapped grid domain.
        # Interior misses need 4 occupied neighbors; edge misses can have 3 occupied
        # neighbors if the missing side points outside the orchard boundary.
        neighbors_4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        missing_trees: List[GpsCoordinate] = []
        
        for row_grid in range(min_row - 1, max_row + 2):
            for col_grid in range(min_col - 1, max_col + 2):
                cell = (row_grid, col_grid)
                
                # Skip if this cell is occupied
                if cell in grid_positions_set:
                    continue
                
                neighbors_of_cell = [
                    (row_grid + 1, col_grid),
                    (row_grid - 1, col_grid),
                    (row_grid, col_grid + 1),
                    (row_grid, col_grid - 1),
                ]

                occupied_neighbors = [n for n in neighbors_of_cell if n in grid_positions_set]
                missing_neighbors = [n for n in neighbors_of_cell if n not in grid_positions_set]

                # Interior candidate: all 4 neighbors occupied.
                # Edge candidates: 3 occupied neighbors (standard boundary case) or
                # 2 occupied orthogonal neighbors (robust to local snap jitter).
                if len(occupied_neighbors) < 2:
                    continue
                if len(occupied_neighbors) == 3:
                    missing_neighbor_r, missing_neighbor_c = missing_neighbors[0]
                    missing_neighbor_m = (
                        centroid_m
                        + (missing_neighbor_r * row_spacing_m * axis_row)
                        + (missing_neighbor_c * tree_spacing_m * axis_col)
                    )
                    missing_neighbor_lat, missing_neighbor_lng = MissingTreesDetector._from_metric_point(
                        missing_neighbor_m,
                        mean_lat_rad,
                    )
                    missing_neighbor_point = Point(missing_neighbor_lng, missing_neighbor_lat)
                    if poly.contains(missing_neighbor_point):
                        # Tolerate slight projection jitter near the boundary.
                        boundary_tolerance_deg = (0.45 * min(row_spacing_m, tree_spacing_m)) / MissingTreesDetector.METERS_PER_DEG_LAT
                        if poly.exterior.distance(missing_neighbor_point) > boundary_tolerance_deg:
                            continue
                elif len(occupied_neighbors) == 2:
                    occupied_offsets = [
                        (neighbor_r - row_grid, neighbor_c - col_grid)
                        for neighbor_r, neighbor_c in occupied_neighbors
                    ]
                    opposite_vertical = (1, 0) in occupied_offsets and (-1, 0) in occupied_offsets
                    opposite_horizontal = (0, 1) in occupied_offsets and (0, -1) in occupied_offsets

                    missing_outside_count = 0
                    for missing_neighbor_r, missing_neighbor_c in missing_neighbors:
                        missing_neighbor_m = (
                            centroid_m
                            + (missing_neighbor_r * row_spacing_m * axis_row)
                            + (missing_neighbor_c * tree_spacing_m * axis_col)
                        )
                        missing_neighbor_lat, missing_neighbor_lng = MissingTreesDetector._from_metric_point(
                            missing_neighbor_m,
                            mean_lat_rad,
                        )
                        if not poly.contains(Point(missing_neighbor_lng, missing_neighbor_lat)):
                            missing_outside_count += 1

                    if opposite_vertical or opposite_horizontal:
                        # Edge-only exception for opposite-neighbor pattern:
                        # allow when exactly one side is outside the polygon and
                        # line continuity is strong (second neighbors exist).
                        if missing_outside_count != 1:
                            continue

                        dr1, dc1 = occupied_offsets[0]
                        dr2, dc2 = occupied_offsets[1]
                        second_1 = (row_grid + 2 * dr1, col_grid + 2 * dc1)
                        second_2 = (row_grid + 2 * dr2, col_grid + 2 * dc2)
                        if second_1 not in grid_positions_set or second_2 not in grid_positions_set:
                            continue
                    else:
                        if missing_outside_count < 1:
                            continue
                elif len(occupied_neighbors) != 4:
                    continue
                
                # Reconstruct candidate in metric space, then convert to lat/lng
                candidate_m = (
                    centroid_m
                    + (row_grid * row_spacing_m * axis_row)
                    + (col_grid * tree_spacing_m * axis_col)
                )
                cand_lat, cand_lng = MissingTreesDetector._from_metric_point(candidate_m, mean_lat_rad)
                
                cand_point = Point(cand_lng, cand_lat)
                
                # Must be inside polygon
                if not poly.contains(cand_point):
                    continue
                
                # Verify no detected tree is within threshold distance
                deltas_m = metric_points - candidate_m
                distances_m = np.sqrt((deltas_m[:, 0] ** 2) + (deltas_m[:, 1] ** 2))
                if float(np.min(distances_m)) < threshold_m:
                    continue
                
                # Additional check: verify that occupied neighbor positions truly map to detected trees
                # (filters false positives when local grid alignment is poor)
                well_aligned_neighbors = 0
                for neighbor_r, neighbor_c in occupied_neighbors:
                    neighbor_m = (
                        centroid_m
                        + (neighbor_r * row_spacing_m * axis_row)
                        + (neighbor_c * tree_spacing_m * axis_col)
                    )
                    # Check if there's a detected tree near the expected neighbor position
                    deltas_to_neighbor = metric_points - neighbor_m
                    dists_to_neighbor = np.sqrt((deltas_to_neighbor[:, 0] ** 2) + (deltas_to_neighbor[:, 1] ** 2))
                    if float(np.min(dists_to_neighbor)) < threshold_m * 1.5:
                        well_aligned_neighbors += 1
                
                required_aligned = 4 if len(occupied_neighbors) == 4 else 2
                if well_aligned_neighbors < required_aligned:
                    continue
                
                missing_trees.append(GpsCoordinate(lat=round(cand_lat, 6), lng=round(cand_lng, 6)))

        logger.info(
            f"Detected {len(missing_trees)} missing trees using metric grid normalization"
        )
        return missing_trees

    @staticmethod
    def _to_metric_points(points_lat_lng: np.ndarray) -> Tuple[np.ndarray, float]:
        mean_lat_rad = float(np.radians(np.mean(points_lat_lng[:, 0])))
        y_m = points_lat_lng[:, 0] * MissingTreesDetector.METERS_PER_DEG_LAT
        x_m = points_lat_lng[:, 1] * MissingTreesDetector.METERS_PER_DEG_LAT * np.cos(mean_lat_rad)
        metric_points = np.column_stack([y_m, x_m])
        return metric_points, mean_lat_rad

    @staticmethod
    def _from_metric_point(point_m: np.ndarray, mean_lat_rad: float) -> Tuple[float, float]:
        lat = float(point_m[0] / MissingTreesDetector.METERS_PER_DEG_LAT)
        lng = float(point_m[1] / (MissingTreesDetector.METERS_PER_DEG_LAT * np.cos(mean_lat_rad)))
        return lat, lng

    @staticmethod
    def _infer_row_direction_from_polygon_metric(polygon: Polygon, mean_lat_rad: float) -> float:
        coords = list(polygon.exterior.coords)
        best_angle = 0.0
        longest = 0.0

        for i in range(len(coords) - 1):
            lng1, lat1 = coords[i]
            lng2, lat2 = coords[i + 1]

            dy = (lat2 - lat1) * MissingTreesDetector.METERS_PER_DEG_LAT
            dx = (lng2 - lng1) * MissingTreesDetector.METERS_PER_DEG_LAT * np.cos(mean_lat_rad)
            length = np.hypot(dy, dx)

            if length > longest:
                longest = length
                best_angle = float(np.arctan2(dy, dx))

        return best_angle

    @staticmethod
    def _refine_row_angle_from_neighbors(metric_points: np.ndarray, seed_angle_rad: float, n_neighbors: int = 6) -> float:
        if len(metric_points) < 3:
            return seed_angle_rad

        angles_deg: List[float] = []
        for i, point in enumerate(metric_points):
            deltas = metric_points - point
            distances = np.linalg.norm(deltas, axis=1)
            distances[i] = np.inf

            nearest_idx = np.argsort(distances)[:n_neighbors]
            for idx in nearest_idx:
                diff = deltas[idx]
                if np.linalg.norm(diff) < 0.01:
                    continue
                angle_deg = float(np.degrees(np.arctan2(diff[0], diff[1])) % 180.0)
                angles_deg.append(angle_deg)

        if not angles_deg:
            return seed_angle_rad

        bins = np.arange(0, 181, 1)
        hist, edges = np.histogram(np.array(angles_deg), bins=bins)
        centers = (edges[:-1] + edges[1:]) / 2.0
        hist_smooth = np.convolve(hist.astype(float), np.ones(5) / 5.0, mode="same")

        seed_deg = float(np.degrees(seed_angle_rad) % 180.0)
        proximity_weight = np.exp(-0.5 * ((centers - seed_deg) / 25.0) ** 2)
        row_deg = float(centers[int(np.argmax(hist_smooth * proximity_weight))])
        return float(np.radians(row_deg))

    @staticmethod
    def _estimate_metric_spacings(
        metric_points: np.ndarray,
        axis_row: np.ndarray,
        axis_col: np.ndarray,
    ) -> Tuple[float, float]:
        if len(metric_points) < 3:
            return 5.0, 5.0

        min_distances: List[float] = []
        for i, point in enumerate(metric_points):
            deltas = metric_points - point
            distances = np.linalg.norm(deltas, axis=1)
            distances[i] = np.inf
            min_distances.append(float(np.min(distances)))

        rough_spacing = float(np.median(np.array(min_distances)))

        proj_row = metric_points @ axis_row
        proj_col = metric_points @ axis_col
        row_indices = np.round(proj_col / rough_spacing).astype(int)

        within_row_gaps: List[float] = []
        row_centers: List[float] = []

        for row_index in np.unique(row_indices):
            mask = row_indices == row_index
            row_projected = np.sort(proj_row[mask])
            row_centers.append(float(np.mean(proj_col[mask])))
            if len(row_projected) < 2:
                continue

            gaps = np.diff(row_projected)
            valid = gaps[(gaps > rough_spacing * 0.5) & (gaps < rough_spacing * 2.5)]
            within_row_gaps.extend([float(value) for value in valid])

        tree_spacing_m = float(np.median(np.array(within_row_gaps))) if within_row_gaps else rough_spacing

        row_centers_sorted = np.array(sorted(row_centers), dtype=float)
        if len(row_centers_sorted) >= 2:
            row_gaps = np.diff(row_centers_sorted)
            valid_row_gaps = row_gaps[(row_gaps > rough_spacing * 0.5) & (row_gaps < rough_spacing * 2.5)]
            row_spacing_m = float(np.median(valid_row_gaps)) if len(valid_row_gaps) else rough_spacing
        else:
            row_spacing_m = rough_spacing

        return row_spacing_m, tree_spacing_m

    @staticmethod
    def _estimate_axis_spacings(
        detected_trees: List[Tuple[float, float]],
        axis_row: np.ndarray,
        axis_col: np.ndarray,
    ) -> Tuple[float, float]:
        """Estimate lattice spacing independently along row/column axes using average local distances."""
        if len(detected_trees) < 3:
            return 0.00005, 0.00005

        points = np.array(detected_trees, dtype=float)
        row_samples: List[float] = []
        col_samples: List[float] = []

        for i, point in enumerate(points):
            deltas = points - point
            distances = np.sqrt((deltas[:, 0] ** 2) + (deltas[:, 1] ** 2))
            distances[i] = np.inf

            nearest_idx = np.argsort(distances)[:8]
            for idx in nearest_idx:
                if not np.isfinite(distances[idx]):
                    continue
                diff = deltas[idx]
                row_component = abs(float(np.dot(diff, axis_row)))
                col_component = abs(float(np.dot(diff, axis_col)))

                if row_component < 1e-9 and col_component < 1e-9:
                    continue

                if row_component >= col_component:
                    row_samples.append(row_component)
                else:
                    col_samples.append(col_component)

        def _average_smallest_cluster(samples: List[float], fallback: float) -> float:
            if not samples:
                return fallback
            values = np.array(sorted(samples), dtype=float)
            cutoff = max(3, int(len(values) * 0.4))
            return float(np.mean(values[:cutoff]))

        row_spacing = _average_smallest_cluster(row_samples, 0.00005)
        col_spacing = _average_smallest_cluster(col_samples, row_spacing)

        return row_spacing, col_spacing

