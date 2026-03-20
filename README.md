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

### 1) Clone repository
```bash
git clone https://github.com/YOUR_USERNAME/tree-count.git
cd tree-count
```

### 2) Create .env from template
```bash
cp .env.example .env
# Edit .env and add your API_KEY
```

### 3) Create and activate virtualenv
```bash
python3.12 -m venv venv
source venv/bin/activate
```

### 4) Install dependencies
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 5) Run API locally
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6) Test endpoint
```bash
# Example curl command from assessment
HOSTNAME="aero-test.my-test-site.com"
curl \
  -X GET \
  -H 'content-type:application/json' \
  https://${HOSTNAME}/orchards/216269/missing-trees

# Or for local testing:
curl http://localhost:8000/orchards/216269/missing-trees

# Generate visualization PNG + metadata
curl http://localhost:8000/orchards/216269/visualization
```

## API endpoints
- `GET /health` → `{"status":"healthy"}`
- `GET /orchards/{orchard_id}/missing-trees` → list of missing coordinates
- `GET /orchards/{orchard_id}/visualization` → generates PNG and returns metadata + image URL
- `GET /outputs/{file}` → serves generated visualization files

### Swagger docs
- http://localhost:8000/docs

## Testing
```bash
pytest tests/ -v
```

## Debugging grid normalization

Use the debug script to inspect normalized grid behavior:

```bash
python scripts/debug_grid.py
```

The script writes a diagnostic image to:

- `outputs/debug-grid-216269.png`

## Docker & Compose
1) Build image:
```bash
docker build -t aerobotics-api:latest .
```
2) Run service:
```bash
docker-compose up -d
```
3) Health check:
```bash
curl http://localhost:8000/health
```

## File purpose summary
- `app/main.py`: API routes, business flow
- `app/aerobotics_client.py`: Aerobotics API client
- `app/missing_trees.py`: metric-grid missing tree detection logic (edge-aware)
- `app/visualization.py`: orchard + detected trees + missing tree rendering
- `app/models.py`: pydantic models
- `app/config.py`: env config with pydantic-settings
- `Dockerfile`/`docker-compose.yml`: containerization
- `scripts/debug_grid.py`: normalization diagnostics and plotting
- `setup-dev.sh`: setup script
- `requirements*.txt`: dependencies
- `pytest.ini`, `setup.cfg`, `pyproject.toml`: testing and lint config

## Notes
- Use `make test`, `make lint`, `make format` for quality checks.
- `orchard_id=216269` is the assessment orchard to test against.

