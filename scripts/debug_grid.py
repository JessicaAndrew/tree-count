#!/usr/bin/env python3
"""Debug: metric space, polygon seed, histogram axis refinement, row-clustered spacing."""

import sys, json
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import matplotlib.pyplot as plt
from app.missing_trees import MissingTreesDetector

CACHE_FILE = PROJECT_ROOT / "outputs" / "debug_cache_216269.json"
METERS_PER_DEG_LAT = 111320.0


def load_data(orchard_id: int = 216269):
    if CACHE_FILE.exists():
        print("Using cached data...")
        with open(CACHE_FILE) as f:
            d = json.load(f)
        return d["polygon_str"], [(t[0], t[1]) for t in d["detected_trees"]]
    from app.aerobotics_client import AeroboticsClient
    client = AeroboticsClient()
    orchard = client.get_orchard(orchard_id)
    survey  = client.get_latest_survey(orchard_id)
    trees   = client.get_tree_surveys(survey["id"])
    data = []
    for t in trees:
        lat = t.get("latitude") or t.get("lat")
        lng = t.get("longitude") or t.get("lng")
        if lat and lng:
            data.append([float(lat), float(lng)])
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump({"polygon_str": orchard.get("polygon",""), "detected_trees": data}, f)
    return orchard.get("polygon",""), [(t[0], t[1]) for t in data]


def to_meters(latlon: np.ndarray):
    mean_lat_rad = np.radians(latlon[:, 0].mean())
    y = latlon[:, 0] * METERS_PER_DEG_LAT
    x = latlon[:, 1] * METERS_PER_DEG_LAT * np.cos(mean_lat_rad)
    return np.column_stack([y, x]), mean_lat_rad


def from_meters(pts_m: np.ndarray, mean_lat_rad: float):
    lat = pts_m[:, 0] / METERS_PER_DEG_LAT
    lng = pts_m[:, 1] / (METERS_PER_DEG_LAT * np.cos(mean_lat_rad))
    return np.column_stack([lat, lng])


def polygon_seed_angle(poly, mean_lat_rad: float):
    """Longest polygon edge angle in metric space (0°=east, 90°=north)."""
    coords = list(poly.exterior.coords)
    best_angle, longest = 0.0, 0.0
    for i in range(len(coords) - 1):
        lng1, lat1 = coords[i];  lng2, lat2 = coords[i+1]
        dy = (lat2 - lat1) * METERS_PER_DEG_LAT
        dx = (lng2 - lng1) * METERS_PER_DEG_LAT * np.cos(mean_lat_rad)
        length = np.hypot(dy, dx)
        if length > longest:
            longest = length
            best_angle = np.arctan2(dy, dx)
    return best_angle


def histogram_row_angle(pts_m: np.ndarray, seed_rad: float, n_neighbors: int = 6):
    """
    Compute inter-tree vector angles in metric space.
    arctan2(dy, dx): 0°=east, 90°=north, folded to [0,180).
    """
    angles = []
    for i, pt in enumerate(pts_m):
        diffs = pts_m - pt
        dists = np.linalg.norm(diffs, axis=1)
        dists[i] = np.inf
        for j in np.argsort(dists)[:n_neighbors]:
            d = diffs[j]
            if np.linalg.norm(d) < 0.01:
                continue
            a = np.degrees(np.arctan2(d[0], d[1])) % 180
            angles.append(a)
    angles = np.array(angles)
    bins = np.arange(0, 181, 1)
    hist, edges = np.histogram(angles, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2
    hist_s = np.convolve(hist.astype(float), np.ones(5)/5, mode='same')
    seed_deg = np.degrees(seed_rad) % 180
    prox = np.exp(-0.5 * ((centers - seed_deg) / 25) ** 2)
    row_deg = float(centers[np.argmax(hist_s * prox)])
    return row_deg, hist_s, centers


def nearest_neighbor_spacing(pts_m: np.ndarray):
    """Median nearest-neighbor distance — gives a robust rough spacing estimate."""
    min_dists = []
    for i, pt in enumerate(pts_m):
        diffs = pts_m - pt
        dists = np.linalg.norm(diffs, axis=1)
        dists[i] = np.inf
        min_dists.append(np.min(dists))
    return float(np.median(min_dists))


def estimate_spacings_m(pts_m: np.ndarray, axis_row_m, axis_col_m):
    """
    Estimate row and tree spacings in meters.
    1. nearest-neighbor median → rough spacing
    2. cluster by axis_col projection into rows
    3. within-row gaps → tree_spacing
    4. between-row gaps → row_spacing
    """
    rough_sp = nearest_neighbor_spacing(pts_m)
    print(f"  Nearest-neighbor median: {rough_sp:.2f}m")

    proj_row = pts_m @ axis_row_m
    proj_col = pts_m @ axis_col_m

    # Assign each tree to a row index by clustering axis_col projections
    row_indices = np.round(proj_col / rough_sp).astype(int)

    within_gaps = []
    row_col_vals = []
    for ri in np.unique(row_indices):
        mask = row_indices == ri
        pts_in_row = np.sort(proj_row[mask])
        row_col_vals.append(np.mean(proj_col[mask]))
        if len(pts_in_row) < 2:
            continue
        gaps = np.diff(pts_in_row)
        valid = gaps[(gaps > rough_sp * 0.5) & (gaps < rough_sp * 2.5)]
        within_gaps.extend(valid)

    tree_sp = float(np.median(within_gaps)) if within_gaps else rough_sp

    # Between-row spacing from consecutive row projections
    row_col_vals = np.array(sorted(row_col_vals))
    if len(row_col_vals) >= 2:
        row_gaps = np.diff(row_col_vals)
        valid_row = row_gaps[(row_gaps > rough_sp * 0.5) & (row_gaps < rough_sp * 2.5)]
        row_sp = float(np.median(valid_row)) if len(valid_row) else rough_sp
    else:
        row_sp = rough_sp

    return row_sp, tree_sp


def snap_and_find_missing(pts_m, axis_row_m, axis_col_m, row_sp, tree_sp, centroid_m):
    grid_cells, raw = set(), []
    for pt in pts_m:
        rel = pt - centroid_m
        ri = np.dot(rel, axis_row_m) / row_sp
        ci = np.dot(rel, axis_col_m) / tree_sp
        rg, cg = int(np.round(ri)), int(np.round(ci))
        raw.append((ri, ci, rg, cg))
        grid_cells.add((rg, cg))

    errors = [np.hypot(ri-rg, ci-cg) for ri, ci, rg, cg in raw]

    rows_idx = [r for r, c in grid_cells];  cols_idx = [c for r, c in grid_cells]
    min_row, max_row = min(rows_idx), max(rows_idx)
    min_col, max_col = min(cols_idx), max(cols_idx)
    print(f"  Grid: {max_row-min_row+1} rows × {max_col-min_col+1} cols = {(max_row-min_row+1)*(max_col-min_col+1)} cells")

    missing = []
    for rg in range(min_row+1, max_row):
        for cg in range(min_col+1, max_col):
            if (rg, cg) not in grid_cells:
                nbrs = [(rg+1,cg),(rg-1,cg),(rg,cg+1),(rg,cg-1)]
                if all(n in grid_cells for n in nbrs):
                    missing.append((rg, cg))

    return grid_cells, raw, errors, missing, (min_row, max_row, min_col, max_col)


def debug_grid_visualization(orchard_id: int = 216269):
    polygon_str, detected_trees = load_data(orchard_id)
    print(f"Trees: {len(detected_trees)}")

    poly = MissingTreesDetector.parse_polygon_string(polygon_str)
    tree_latlon = np.array(detected_trees)
    pts_m, mean_lat_rad = to_meters(tree_latlon)
    centroid_m = pts_m.mean(axis=0)

    seed_rad = polygon_seed_angle(poly, mean_lat_rad)
    seed_deg = np.degrees(seed_rad) % 180
    print(f"Seed: {seed_deg:.2f}°")

    row_deg, hist_s, centers = histogram_row_angle(pts_m, seed_rad)
    col_deg = (row_deg + 90) % 180
    print(f"Row: {row_deg:.2f}°   Col (⊥): {col_deg:.2f}°")

    a_row, a_col = np.radians(row_deg), np.radians(col_deg)
    axis_row_m = np.array([np.sin(a_row), np.cos(a_row)])
    axis_col_m = np.array([np.sin(a_col), np.cos(a_col)])

    row_sp, tree_sp = estimate_spacings_m(pts_m, axis_row_m, axis_col_m)
    print(f"Row spacing: {row_sp:.2f}m   Tree spacing: {tree_sp:.2f}m")

    grid_cells, raw, errors, missing, bounds = snap_and_find_missing(
        pts_m, axis_row_m, axis_col_m, row_sp, tree_sp, centroid_m
    )
    min_row, max_row, min_col, max_col = bounds

    print(f"Snap error  mean={np.mean(errors):.4f}  max={np.max(errors):.4f}")
    print(f"Interior missing: {len(missing)}")

    # ---- 3-panel plot ----
    fig, axes_p = plt.subplots(1, 3, figsize=(22, 8))

    ax = axes_p[0]
    ax.scatter(tree_latlon[:,1], tree_latlon[:,0], s=15, alpha=0.4, color='steelblue')
    px, py = poly.exterior.xy
    ax.plot(px, py, 'k-', lw=1.5)
    ctr_gps = from_meters(centroid_m[None], mean_lat_rad)[0]
    scale_m = row_sp * 15
    def arrow_gps(axis_m):
        end_m = centroid_m + axis_m * scale_m
        return from_meters(end_m[None], mean_lat_rad)[0]
    e_row = arrow_gps(axis_row_m);  e_col = arrow_gps(axis_col_m)
    ax.annotate("", xy=(e_row[1], e_row[0]), xytext=(ctr_gps[1], ctr_gps[0]),
                arrowprops=dict(arrowstyle='->', color='red', lw=2.5))
    ax.annotate("", xy=(e_col[1], e_col[0]), xytext=(ctr_gps[1], ctr_gps[0]),
                arrowprops=dict(arrowstyle='->', color='green', lw=2.5))
    ax.set_title(f"GPS  Row={row_deg:.1f}° (red)  Col={col_deg:.1f}° (green)")
    ax.set_aspect('equal'); ax.grid(True, alpha=0.3)
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")

    ax = axes_p[1]
    ax.bar(centers, hist_s, width=1, alpha=0.6, color='steelblue')
    ax.axvline(seed_deg, color='orange', lw=2, ls='--', label=f'Seed {seed_deg:.1f}°')
    ax.axvline(row_deg,  color='red',    lw=2.5, label=f'Row {row_deg:.1f}°')
    ax.axvline(col_deg,  color='green',  lw=2.5, ls=':', label=f'Col {col_deg:.1f}°')
    ax.set_xlabel("Angle [0°=east, 90°=north, folded 0–180°]"); ax.set_ylabel("Count")
    ax.set_title("Inter-tree metric angle histogram"); ax.legend(); ax.grid(True, alpha=0.3)

    ax = axes_p[2]
    gp = np.array([(ci, ri) for ri, ci, rg, cg in raw])
    ax.scatter(gp[:,0], gp[:,1], s=15, alpha=0.4, color='steelblue', label='Trees')
    for r in range(min_row, max_row+1):
        ax.axhline(r, color='gray', ls='--', alpha=0.2, lw=0.4)
    for c in range(min_col, max_col+1):
        ax.axvline(c, color='gray', ls='--', alpha=0.2, lw=0.4)
    if missing:
        ax.scatter([c for r,c in missing],[r for r,c in missing],
                   s=80, color='red', zorder=5, label=f'Missing ({len(missing)})')
    ax.set_title(f"Normalised Grid  snap={np.mean(errors):.3f}  missing={len(missing)}")
    ax.set_xlabel("Column index"); ax.set_ylabel("Row index")
    ax.legend(); ax.set_aspect('equal'); ax.grid(True, alpha=0.3)

    plt.tight_layout()
    out = PROJECT_ROOT / "outputs" / f"debug-grid-{orchard_id}.png"
    plt.savefig(out, dpi=150, bbox_inches='tight')
    print(f"Saved → {out}")


if __name__ == "__main__":
    debug_grid_visualization()
