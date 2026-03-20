.PHONY: help install install-dev test test-cov lint format run docker-build docker-up docker-down clean

help:
	@echo "Aerobotics Missing Trees API - Available Commands"
	@echo ""
	@echo "Development:"
	@echo "  make install         Install dependencies"
	@echo "  make install-dev     Install dev dependencies"
	@echo "  make test            Run tests"
	@echo "  make test-cov        Run tests with coverage"
	@echo "  make lint            Run linting checks"
	@echo "  make format          Format code with black and isort"
	@echo ""
	@echo "Running:"
	@echo "  make run             Run development server"
	@echo "  make run-prod        Run production server"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build    Build Docker image"
	@echo "  make docker-up       Start Docker containers"
	@echo "  make docker-down     Stop Docker containers"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean           Remove cache and temporary files"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt -r requirements-dev.txt

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=app --cov-report=html

lint:
	flake8 app tests
	mypy app --ignore-missing-imports

format:
	black app tests
	isort app tests

run:
	python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-prod:
	gunicorn --bind 0.0.0.0:8000 --workers 4 --timeout 60 app.main:app

docker-build:
	docker build -t aerobotics-api:latest .

docker-up:
	docker-compose up -d
	docker-compose logs -f

docker-down:
	docker-compose down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.py[cod]" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build dist htmlcov .coverage

.DEFAULT_GOAL := help
