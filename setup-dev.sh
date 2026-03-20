#!/bin/bash
# Development setup script

set -e

echo "Setting up Aerobotics Missing Trees API ..."

# Resolve python executable
PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "Error: Python is not installed or not on PATH."
    exit 1
fi

# Create virtual environment in .venv
"${PYTHON_BIN}" -m venv .venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Copy .env template
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file - please configure your API key"
fi

echo "Setup complete!"
echo ""
echo "To start the server:"
echo "  source .venv/bin/activate"
echo "  python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "To run tests:"
echo "  pytest tests/ -v"
echo ""
echo "To build and run with Docker:"
echo "  docker-compose up"
