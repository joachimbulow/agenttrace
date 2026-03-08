.PHONY: dev backend frontend install test clean docker-up docker-down

# Development
dev: backend frontend

backend:
	cd backend && uvicorn agent_trace.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

# Installation
install:
	cd backend && pip install -e ".[dev]"
	cd sdk && pip install -e ".[dev]"
	cd frontend && npm install

# Testing
test:
	cd backend && pytest
	cd sdk && pytest

test-unit:
	cd backend && pytest tests/unit/ -v

test-integration:
	cd backend && pytest tests/integration/ -v

# Docker
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-build:
	docker-compose build

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf frontend/node_modules frontend/dist
	rm -rf data/*.db

# Full stack
all: install docker-up
	@echo "Services started:"
	@echo "  Backend: http://localhost:8000"
	@echo "  Frontend: http://localhost:3000"
	@echo "  API Docs: http://localhost:8000/docs"