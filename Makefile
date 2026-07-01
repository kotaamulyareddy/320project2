.PHONY: help build up down restart logs ps clean test migrate-create migrate-apply setup-dev

help:
	@echo "=========================================================================="
	@echo "Distributed Real-Time Video Analytics Pipeline & Edge AI Event Engine"
	@echo "=========================================================================="
	@echo "Commands:"
	@echo "  build            Build all Docker containers"
	@echo "  up               Run all services in background"
	@echo "  down             Stop and remove all containers"
	@echo "  restart          Restart all services"
	@echo "  logs             Tail container logs"
	@echo "  ps               Show running container status"
	@echo "  clean            Stop containers and clean volumes/caches"
	@echo "  test             Run all backend unit tests"
	@echo "  migrate-create   Generate a database migration (e.g., make migrate-create msg='initial')"
	@echo "  migrate-apply    Apply pending database migrations"
	@echo "  setup-dev        Install Python dev requirements and frontend packages"
	@echo "=========================================================================="

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

ps:
	docker compose ps

clean:
	docker compose down -v
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf frontend/dist frontend/node_modules

test:
	docker compose run --rm api_gateway pytest app/tests/

migrate-create:
	docker compose run --rm api_gateway alembic revision --autogenerate -m "$(msg)"

migrate-apply:
	docker compose run --rm api_gateway alembic upgrade head

setup-dev:
	pip install -r requirements-dev.txt
	cd frontend && npm install
