.DEFAULT_GOAL := help
SHELL := /bin/bash
COMPOSE := docker compose

.PHONY: help up down reset logs ps psql test lint shell-backend shell-frontend rebuild

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up: ## Start all services (db, backend, frontend)
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")
	$(COMPOSE) up -d --build
	@echo ""
	@echo "  frontend  http://localhost:5173"
	@echo "  backend   http://localhost:8000/health/db"
	@echo "  docs      http://localhost:8000/docs"

down: ## Stop all services (keeps data)
	$(COMPOSE) down

reset: ## DESTROY the database volume and re-run db/init/*.sql from scratch
	$(COMPOSE) down -v
	$(COMPOSE) up -d --build
	@echo "Waiting for database to initialise..."
	@until docker exec ksp_db pg_isready -U $${POSTGRES_USER:-ksp} -q 2>/dev/null; do sleep 1; done
	@sleep 2
	@$(MAKE) --no-print-directory tables

tables: ## List all tables in both schemas
	@docker exec ksp_db psql -U $${POSTGRES_USER:-ksp} -d $${POSTGRES_DB:-ksp_crime} \
		-c "\dt ksp.*" -c "\dt derived.*"

psql: ## Open a psql shell
	docker exec -it ksp_db psql -U $${POSTGRES_USER:-ksp} -d $${POSTGRES_DB:-ksp_crime}

logs: ## Tail logs from all services
	$(COMPOSE) logs -f

ps: ## Show service status
	$(COMPOSE) ps

test: ## Run the backend test suite
	docker exec ksp_backend pytest

lint: ## Lint backend and typecheck frontend
	docker exec ksp_backend ruff check .
	docker exec ksp_frontend npm run lint

shell-backend: ## Shell into the backend container
	docker exec -it ksp_backend bash

shell-frontend: ## Shell into the frontend container
	docker exec -it ksp_frontend sh

rebuild: ## Force a rebuild of both app images
	$(COMPOSE) build --no-cache backend frontend
	$(COMPOSE) up -d
