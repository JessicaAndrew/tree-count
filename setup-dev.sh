#!/bin/bash
# Development setup script

set -e

echo "Setting up Aerobotics Missing Trees API ..."

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

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
echo "  source venv/bin/activate"
echo "  python -m uvicorn app.main:app --reload"
echo ""
echo "To run tests:"
echo "  pytest tests/ -v"
echo ""
echo "To build and run with Docker:"
echo "  docker-compose up"
