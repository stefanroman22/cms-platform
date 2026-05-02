# Makefile — single entry point for the CMS monorepo.
# `make help` lists every target.
#
# Cross-platform notes:
#   • Windows Git Bash users: venv binaries live in `backend/venv/Scripts/`.
#   • macOS/Linux users: venv binaries live in `backend/venv/bin/`.
#   The PY_BIN variable below auto-detects which one exists.

SHELL := /bin/bash
.DEFAULT_GOAL := help

PY ?= python
BACKEND_VENV ?= backend/venv
# Auto-detect Windows Scripts/ vs Unix bin/.
PY_BIN := $(shell test -d "$(BACKEND_VENV)/Scripts" && echo "$(BACKEND_VENV)/Scripts" || echo "$(BACKEND_VENV)/bin")

# ── Help ─────────────────────────────────────────────────────────────────
.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Available targets:\n"} /^[a-zA-Z0-9_-]+:.*##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ── First-time setup ─────────────────────────────────────────────────────
.PHONY: install
install: ## Install all dependencies (backend, agent, frontend, pre-commit)
	$(PY) -m venv $(BACKEND_VENV)
	$(PY_BIN)/pip install -r backend/requirements.txt -r backend/requirements-dev.txt
	$(PY_BIN)/pip install -r "agents/CMS Connector - Website/requirements.txt" -r "agents/CMS Connector - Website/requirements-dev.txt"
	cd frontend && npm ci
	$(PY) -m pip install --user pre-commit==4.0.1
	pre-commit install

.PHONY: env
env: ## Interactive: copy .env.example → .env and prompt for required values
	bash scripts/init-env.sh

# ── Daily workflow ───────────────────────────────────────────────────────
.PHONY: dev
dev: ## Print the two terminal commands to run for backend + frontend dev servers
	@echo "Run these in two terminals:"
	@echo "  Terminal 1:  $(PY_BIN)/uvicorn auth_service.main:app --reload --port 8001 --app-dir backend"
	@echo "  Terminal 2:  cd frontend && npm run dev"

.PHONY: test
test: test-backend test-agent test-frontend ## Run every test suite

.PHONY: test-backend
test-backend: ## Run the backend pytest suite
	cd backend && ../$(PY_BIN)/python -m pytest auth_service/tests/ -q

.PHONY: test-agent
test-agent: ## Run the CMS Connector agent test suite
	cd "agents/CMS Connector - Website" && ../../$(PY_BIN)/python -m pytest tests/ -q

.PHONY: test-frontend
test-frontend: ## Run the frontend vitest suite
	cd frontend && npm test

# ── Lint + format ────────────────────────────────────────────────────────
.PHONY: lint
lint: ## Lint everything (ruff + black --check + frontend lint + format:check + typecheck)
	$(PY_BIN)/python -m ruff check .
	$(PY_BIN)/python -m black --check .
	cd frontend && npm run lint && npm run format:check && npm run typecheck

.PHONY: format
format: ## Auto-format everything (ruff --fix, black, prettier)
	$(PY_BIN)/python -m ruff check --fix .
	$(PY_BIN)/python -m black .
	cd frontend && npm run format

# ── CI emulation (run before push) ───────────────────────────────────────
.PHONY: ci
ci: lint test ## Run the same checks as GitHub Actions
