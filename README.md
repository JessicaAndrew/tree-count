# Aerobotics Missing Trees API

## Overview

This project is a FastAPI service that identifies missing trees in orchards using Aerobotics survey data.

- Primary endpoint: `/orchards/{orchard_id}/missing-trees`
- Visualization endpoint: `/orchards/{orchard_id}/visualization`
- Sample orchard ID: `216269`

### Algorithm

The missing tree detection works as follows:

1. **Parse Polygon**: Converts orchard boundary from Aerobotics API format `"lng,lat lng,lat ..."` to geometric polygon
2. **Metric Projection**: Converts lat/lng to local metric coordinates (meters) to avoid longitude/latitude scale distortion
3. **Find Grid Orientation**:
	- Seed direction from the orchard’s longest polygon edge
	- Refine row direction from inter-tree neighbor angle distribution
	- Force a perpendicular second axis
4. **Estimate Spacing**: Derives row/tree spacing from observed nearest-neighbor and row-clustered gaps
5. **Snap to Grid**: Snaps detected trees to integer grid cells in normalized space
6. **Detect Missing Cells**:
	- Interior: requires 4-neighbor support
	- Edge: supports 3-neighbor and selected 2-neighbor boundary patterns with boundary/continuity checks
7. **Return Missing**: Converts accepted missing cells back to GPS coordinates

This approach is robust to rotated orchards, non-rectangular boundaries, and boundary edge cases.

## Quick Start (Development)

### 1) Create .env, with the following format
```bash
# Aerobotics API Configuration
API_KEY=<YOUR_KEY>
APP_NAME="Aerobotics Missing Trees API"
ENVIRONMENT=development
DEBUG=false
API_BASE_URL=https://api.aerobotics.com
```

### 2) Create and activate virtualenv
```bash
python3.12 -m venv venv
source venv/bin/activate
```

### 3) Install dependencies
```bash
make install-dev
```

### 4) Run API locally
```bash
make run
```

### 5) Test endpoint
```bash
# For local testing
curl http://localhost:8000/orchards/216269/missing-trees

# Generate visualisation PNG + metadata
curl http://localhost:8000/orchards/216269/visualization
```

## API endpoints
- `GET /health` → `{"status":"healthy"}`
- `GET /orchards/{orchard_id}/missing-trees` → list of missing tree coordinates
- `GET /orchards/{orchard_id}/visualization` → generates PNG and returns metadata + image URL

### Visualization output location
- The `/orchards/{orchard_id}/visualization` endpoint writes the image to `outputs/orchard-{orchard_id}.png` on the running server.
- It returns `image_url` as `/outputs/orchard-{orchard_id}.png` (for local runs: `http://localhost:8000/outputs/orchard-{orchard_id}.png`).
- On Render, this file is stored on ephemeral instance disk and may be removed after restart/redeploy/sleep (`https://tree-count-8oxw.onrender.com/outputs/orchard-216269.png`).

### Swagger docs
- http://localhost:8000/docs

## Testing
```bash
make test
```

## Debugging grid normalisation

Use the debug script to inspect normalised grid behavior:

```bash
python scripts/debug_grid.py
```

The script writes a diagnostic image to:

- `outputs/debug-grid-216269.png`

## Docker & Compose
1) Build image:
```bash
make docker-build
```
2) Run service:
```bash
make docker-up
```
3) Health check:
```bash
curl http://localhost:8000/health
```

3) Missing trees:
```bash
curl http://localhost:8000/orchards/216269/missing-trees
```

## Deploy on Render (Public URL)

1) Create a Render Web Service:
    - Render Dashboard → **New** → **Web Service**
    - Connect your GitHub repository
    - Select branch: `main`
    - Runtime: `Docker`

2) Set environment variables in Render:
```bash
API_KEY=<YOUR_KEY>
APP_NAME="Aerobotics Missing Trees API"
ENVIRONMENT=development
DEBUG=false
API_BASE_URL=https://api.aerobotics.com
```

3) Wait for deploy to become live, then verify:
```bash
curl https://<your-service>.onrender.com/health
curl https://<your-service>.onrender.com/orchards/216269/missing-trees
```

4) Assessment command format:
```bash
HOSTNAME="tree-count-8oxw.onrender.com"
curl \
	-X GET \
	-H 'content-type:application/json' \
	https://${HOSTNAME}/orchards/216269/missing-trees
```

Notes:
- Render free instances may cold-start after inactivity.
- Each push to your selected branch can auto-trigger redeploys.

## File purpose summary
- `app/main.py`: API routes, business flow
- `app/aerobotics_client.py`: Aerobotics API client
- `app/missing_trees.py`: metric-grid missing tree detection logic (edge-aware)
- `app/visualization.py`: orchard + detected trees + missing tree rendering
- `app/models.py`: pydantic models
- `app/config.py`: env config with pydantic-settings
- `Dockerfile`/`docker-compose.yml`: containerisation
- `scripts/debug_grid.py`: normalisation diagnostics and plotting
- `setup-dev.sh`: setup script
- `requirements*.txt`: dependencies
- `pytest.ini`, `setup.cfg`, `pyproject.toml`: testing and lint config

## Notes
- Use `make test`, `make lint`, `make format` for quality checks.
- `orchard_id=216269` is the assessment orchard to test against.

