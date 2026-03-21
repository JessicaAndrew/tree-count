""" Utilities for rendering orchard and tree detections as an image. """

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app.aerobotics_client import AeroboticsClient
from app.missing_trees import MissingTreesDetector


def _parse_polygon_string(polygon_str: str) -> List[Tuple[float, float]]:
    """ Parse polygon string format: 'lng,lat lng,lat ...' into (lng, lat). """
    points: List[Tuple[float, float]] = []
    for pair in polygon_str.strip().split():
        lng_raw, lat_raw = pair.split(",")
        points.append((float(lng_raw), float(lat_raw)))
    
    return points


def _extract_tree_points(tree_surveys: List[dict]) -> List[Tuple[float, float]]:
    """ Extract tree points as (lng, lat) from survey payload. """
    points: List[Tuple[float, float]] = []
    for tree in tree_surveys:
        lat = tree.get("lat", tree.get("latitude"))
        lng = tree.get("lng", tree.get("longitude"))
        if lat is None or lng is None:
            continue
        points.append((float(lng), float(lat)))
        
    return points


def _extract_detected_trees(tree_surveys: List[dict]) -> List[Tuple[float, float]]:
    """ Extract tree points as (lat, lng) for missing-tree detector input. """
    points: List[Tuple[float, float]] = []
    for tree in tree_surveys:
        lat = tree.get("lat", tree.get("latitude"))
        lng = tree.get("lng", tree.get("longitude"))
        if lat is None or lng is None:
            continue
        points.append((float(lat), float(lng)))
    
    return points


def build_orchard_visualization(orchard_id: int, output: Path) -> Dict[str, int | str]:
    """ Fetch orchard + trees and save a PNG visualization.

        Returns metadata about the generated image.
    """
    client = AeroboticsClient()

    orchard = client.get_orchard(orchard_id)
    latest_survey = client.get_latest_survey(orchard_id)
    if not latest_survey:
        raise RuntimeError(f"No surveys found for orchard {orchard_id}")

    survey_id = int(latest_survey["id"])
    tree_surveys = client.get_tree_surveys(survey_id)

    polygon_str = orchard.get("polygon")
    if not polygon_str:
        raise RuntimeError(f"Orchard {orchard_id} has no polygon field")

    polygon_points = _parse_polygon_string(polygon_str)
    tree_points = _extract_tree_points(tree_surveys)
    detected_trees = _extract_detected_trees(tree_surveys)

    missing_trees = MissingTreesDetector.detect_missing_trees(
        orchard_polygon=polygon_str,
        detected_trees=detected_trees,
    )

    polygon_x = [pt[0] for pt in polygon_points]
    polygon_y = [pt[1] for pt in polygon_points]

    fig, ax = plt.subplots(figsize=(10, 10))
    ax.plot(polygon_x, polygon_y, color="#f59e0b", linewidth=2.5, label="Orchard boundary")
    ax.fill(polygon_x, polygon_y, color="#fbbf24", alpha=0.18)

    if tree_points:
        tree_x = [pt[0] for pt in tree_points]
        tree_y = [pt[1] for pt in tree_points]
        ax.scatter(tree_x, tree_y, s=10, color="#2563eb", alpha=0.75, label=f"Trees ({len(tree_points)})")

    if missing_trees:
        missing_x = [tree.lng for tree in missing_trees]
        missing_y = [tree.lat for tree in missing_trees]
        ax.scatter(
            missing_x,
            missing_y,
            s=20,
            color="#dc2626",
            alpha=0.9,
            label=f"Missing trees ({len(missing_trees)})",
            zorder=5,
        )

    ax.set_title(f"Orchard {orchard_id} • Survey {survey_id}")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.legend(loc="best")
    ax.grid(alpha=0.2)
    ax.set_aspect("equal", adjustable="box")

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output, dpi=200)
    plt.close(fig)

    return {
        "orchard_id": orchard_id,
        "survey_id": survey_id,
        "tree_count": len(tree_points),
        "missing_count": len(missing_trees),
        "output_path": str(output),
    }
