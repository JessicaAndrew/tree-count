# Aerobotics Missing Trees API TODO

Single-document guide for local setup, API usage, and deployment.

## Overview

This project is a Python FastAPI service to identify missing trees in orchards via the Aerobotics API.
- Endpoint: `/orchards/{orchard_id}/missing-trees`
- Sample orchard ID for challenge: `216269`

### Algorithm

The missing tree detection works as follows:

1. **Parse Polygon**: Converts orchard boundary from Aerobotics API format `"lng,lat lng,lat ..."` to geometric polygon
2. **Infer Row Direction**: Uses PCA (Principal Component Analysis) on detected trees to determine planting row alignment (E-W, N-S, or rotated)
3. **Generate Expected Grid**: Creates regular grid of tree positions aligned with row direction, constrained inside polygon boundary
4. **Match Trees**: Compares expected positions with detected trees (within configurable distance threshold)
5. **Return Missing**: GPS coordinates of expected positions without nearby detected trees

This approach correctly handles **irregular orchard boundaries** (trapezoids, non-rectangular shapes) unlike simple bounding-box methods.

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
```

## API endpoints
- `GET /health` → `{"status":"healthy"}`
- `GET /orchards/{orchard_id}/missing-trees` → list of missing coordinates

### Swagger docs
- http://localhost:8000/docs

## Testing
```bash
pytest tests/ -v
```

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

## Deployment (recommended pattern)
### AWS EC2 / general Linux
1. Install Docker + Docker Compose
2. Clone repo, copy `.env` value
3. `docker-compose up -d`

### Heroku
```bash
heroku login
heroku create aerobotics-missing-trees
heroku config:set API_KEY=your_key
git push heroku main
```

### DigitalOcean App Platform
- Connect repo and set `API_KEY` in environment
- Build command: `pip install -r requirements.txt`
- Run command: `gunicorn --bind 0.0.0.0:8000 app.main:app`

## File purpose summary
- `app/main.py`: API routes, business flow
- `app/aerobotics_client.py`: Aerobotics API client
- `app/missing_trees.py`: grid-based missing tree detection
- `app/models.py`: pydantic models
- `app/config.py`: env config with pydantic-settings
- `Dockerfile`/`docker-compose.yml`: containerization
- `setup-dev.sh`: setup script
- `requirements*.txt`: dependencies
- `pytest.ini`, `setup.cfg`, `pyproject.toml`: testing and lint config
- `DEPLOYMENT.md`/`QUICK_START.md`: more details (already shipped)

## Notes
- Use `make test`, `make lint`, `make format` for quality checks.
- `orchard_id=216269` is the assessment orchard to test against.

