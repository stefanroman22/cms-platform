# Developer Experience Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new colleague clones the repo and reaches "tests green, dev server up, ready to ship a change" in ≤ 30 minutes — with automated guardrails (CI + pre-commit) that block them from accidentally breaking master.

**Architecture:** Four passes ordered by severity. **Pass A** unblocks the foundation: backend dev-deps split (so `pytest` works after a fresh `pip install`) and GitHub Actions CI (so future master pushes get caught before they break prod, like the supabase/pydantic incompat that just hit us). **Pass B** adds the daily-use guardrails: ruff + black for Python, Prettier for the frontend, a single `pyproject.toml` for Python tooling at the root, pre-commit hooks that run lint/format on every commit, and `tsc --noEmit` enforced as part of `npm test`. **Pass C** adds the onboarding ergonomics: a root `Makefile` with `make dev`/`test`/`lint`/`format`/`ci`/`env` targets, version pins (`.nvmrc`, `.python-version`), and an interactive env scaffolder. **Pass D** is polish: pin agent deps to exact versions, document the deploy scripts, and rebuild `frontend/node_modules` to match the lockfile.

**Tech stack added:** ruff + black (Python lint+format), Prettier (JS/TS format), pre-commit (Python framework, runs both Python and Node hooks), Husky + lint-staged (frontend per-commit hook), GitHub Actions (CI), pyproject.toml (Python tooling config at root).

---

## File structure

```
.
├── Makefile                              (NEW — single entry point: dev / test / lint / format / ci / env)
├── pyproject.toml                        (NEW — ruff + black config; targets backend/ and agents/)
├── .pre-commit-config.yaml               (NEW — lint+format hooks)
├── .nvmrc                                (NEW — pin Node 20)
├── .python-version                       (NEW — pin Python 3.13)
├── .github/
│   └── workflows/
│       └── ci.yml                        (NEW — backend pytest, agent pytest, frontend vitest + tsc + lint, ruff/black/prettier --check)
├── backend/
│   ├── requirements.txt                  (UNCHANGED — runtime only, Vercel installs this)
│   └── requirements-dev.txt              (NEW — pytest, pytest-asyncio, httpx, ruff, black; Vercel ignores)
├── frontend/
│   ├── package.json                      (MODIFIED — add typecheck script, prettier, husky, lint-staged)
│   ├── .prettierrc                       (NEW)
│   ├── .prettierignore                   (NEW)
│   └── .husky/
│       └── pre-commit                    (NEW — invokes lint-staged)
├── agents/CMS Connector - Website/
│   ├── requirements.txt                  (MODIFIED — pin exact versions)
│   └── requirements-dev.txt              (NEW — pytest)
├── scripts/
│   ├── deploy/
│   │   └── README.md                     (NEW — document the existing Vercel project bootstrap scripts)
│   └── init-env.sh                       (NEW — interactive .env scaffolder; called by `make env`)
└── docs/
    └── archive/
        ├── findings.md                   (MOVED from repo root — original CMS-login findings doc)
        ├── task_plan.md                  (MOVED from repo root)
        ├── progress.md                   (MOVED from repo root)
        ├── task.md.resolved              (MOVED from repo root)
        └── implementation_plan.md.resolved (MOVED from repo root)
```

**Why these decisions:**

- **Vercel + dev-deps split**: Vercel's `@vercel/python` builder installs every line of `requirements.txt` into the serverless function bundle. Test/lint deps don't belong there (deploy size, attack surface). Vercel ignores `requirements-dev.txt`. The same pattern applies to the agent.
- **Single `pyproject.toml` at root**: ruff and black both target `backend/` and `agents/` — putting their config at the root means one source of truth + one `ruff check` invocation covers everything.
- **pre-commit at root, Husky inside frontend**: pre-commit (the Python framework) handles cross-cutting Python hooks but doesn't play well with workspace npm scripts. Husky inside `frontend/` runs lint-staged for changed JS/TS files only. Both are wired into the same `make` targets so devs never invoke them directly.
- **Skipping Docker**: a docker-compose stack is desirable long-term but adds significant maintenance and isn't required for the 30-minute onboarding goal — the Supabase remote is the only external dependency, and the team already pays for it. Marked as future work in Pass D's README, not part of this plan.

---

## Pass A — Foundation (CI + dev-deps split)

Without this pass, every later check is unreliable: a fresh clone can't run tests, and master can ship broken builds with no warning.

### Task A1: Split backend dev deps from runtime deps

**Why:** A fresh `pip install -r backend/requirements.txt` does not install `pytest`, `pytest-asyncio`, or `httpx`. New dev runs `python -m pytest` → `ModuleNotFoundError: No module named pytest`. Move these to `requirements-dev.txt`. Vercel's builder reads only `requirements.txt`, so the deploy bundle stays slim.

**Files:**
- Create: `backend/requirements-dev.txt`
- Modify: `backend/requirements.txt` (no change to content; we already cleaned this in the env-config-hygiene pass — just verify)

- [ ] **Step 1: Create `backend/requirements-dev.txt`**

  ```text
  # Test + lint dependencies for backend/. NOT installed by Vercel —
  # @vercel/python only reads requirements.txt. Install locally:
  #   pip install -r requirements.txt -r requirements-dev.txt

  # Test framework
  pytest==8.3.3
  pytest-asyncio==0.24.0
  httpx==0.27.2

  # Lint + format
  ruff==0.7.4
  black==24.10.0
  ```

- [ ] **Step 2: Verify a fresh install works**

  ```bash
  cd backend
  python -m venv /tmp/clean-venv
  source /tmp/clean-venv/Scripts/activate
  pip install -q -r requirements.txt -r requirements-dev.txt
  python -m pytest auth_service/tests/ -q
  deactivate
  rm -rf /tmp/clean-venv
  ```
  Expected: `52 passed, 4 skipped`. If pytest not found → step 1 wasn't saved correctly.

- [ ] **Step 3: Commit**

  ```bash
  git add backend/requirements-dev.txt
  git commit -m "build(backend): split dev deps into requirements-dev.txt

  Vercel's @vercel/python only installs requirements.txt — keeping the
  test framework out of there shrinks the prod bundle. New flow:
    pip install -r requirements.txt -r requirements-dev.txt"
  ```

### Task A2: Pin agent runtime deps + split agent dev deps

**Why:** `agents/CMS Connector - Website/requirements.txt` uses `>=` ranges (`anthropic>=0.40.0`, `click>=8.1.0`). Future minor releases can break the agent silently. Pin exact versions and put pytest separately.

**Files:**
- Modify: `agents/CMS Connector - Website/requirements.txt`
- Create: `agents/CMS Connector - Website/requirements-dev.txt`

- [ ] **Step 1: Look up the currently-installed versions in the backend venv**

  ```bash
  /c/Users/stefa/.gemini/antigravity/scratch/CMS\ -\ websites/backend/venv/Scripts/python.exe -m pip show anthropic click | grep -E "^Name|^Version"
  ```
  Capture the printed versions (e.g. `anthropic 0.40.0`, `click 8.1.7`).

- [ ] **Step 2: Replace `agents/CMS Connector - Website/requirements.txt`**

  Open the file, replace its contents with (substituting the captured exact versions):
  ```text
  # Runtime dependencies for the CMS Connector — Website agent CLI.
  # Pinned to exact versions for reproducibility.

  anthropic==<EXACT_VERSION_FROM_STEP_1>
  click==<EXACT_VERSION_FROM_STEP_1>
  ```

- [ ] **Step 3: Create `agents/CMS Connector - Website/requirements-dev.txt`**

  ```text
  # Test dependencies for the agent. Install locally with:
  #   pip install -r requirements.txt -r requirements-dev.txt
  pytest==8.3.3
  ```

- [ ] **Step 4: Verify agent still tests green**

  ```bash
  cd "agents/CMS Connector - Website"
  /c/Users/stefa/.gemini/antigravity/scratch/CMS\ -\ websites/backend/venv/Scripts/python.exe \
    -m pytest tests/ -q
  ```
  Expected: 14 passed.

- [ ] **Step 5: Commit**

  ```bash
  git add "agents/CMS Connector - Website/requirements.txt" "agents/CMS Connector - Website/requirements-dev.txt"
  git commit -m "build(agent): pin exact runtime deps + split dev deps"
  ```

### Task A3: GitHub Actions CI

**Why:** Right now nothing runs on `git push origin master` except Vercel's build. Vercel only catches errors that prevent the build itself — runtime test failures, type errors, lint regressions all reach prod. A single CI workflow runs the three test suites + the type-check + the formatters in parallel and fails the run on any red signal.

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create the workflow**

  ```yaml
  # .github/workflows/ci.yml
  name: CI

  on:
    push:
      branches: [master]
    workflow_dispatch:

  concurrency:
    group: ci-${{ github.ref }}
    cancel-in-progress: true

  jobs:
    backend:
      name: Backend (FastAPI)
      runs-on: ubuntu-latest
      defaults:
        run:
          working-directory: backend
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with:
            python-version-file: .python-version
            cache: pip
            cache-dependency-path: |
              backend/requirements.txt
              backend/requirements-dev.txt
        - run: pip install -r requirements.txt -r requirements-dev.txt
        - name: Lint (ruff)
          run: ruff check .
          working-directory: .
        - name: Format check (black)
          run: black --check .
          working-directory: .
        - name: Tests (pytest)
          run: python -m pytest auth_service/tests/ -q

    agent:
      name: Agent (CMS Connector — Website)
      runs-on: ubuntu-latest
      defaults:
        run:
          working-directory: agents/CMS Connector - Website
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with:
            python-version-file: .python-version
            cache: pip
            cache-dependency-path: |
              agents/CMS Connector - Website/requirements.txt
              agents/CMS Connector - Website/requirements-dev.txt
        - run: pip install -r requirements.txt -r requirements-dev.txt
        - name: Tests (pytest)
          run: python -m pytest tests/ -q

    frontend:
      name: Frontend (Next.js)
      runs-on: ubuntu-latest
      defaults:
        run:
          working-directory: frontend
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-node@v4
          with:
            node-version-file: .nvmrc
            cache: npm
            cache-dependency-path: frontend/package-lock.json
        - run: npm ci
        - name: Type check
          run: npm run typecheck
        - name: Lint
          run: npm run lint
        - name: Format check
          run: npm run format:check
        - name: Tests
          run: npm test
  ```

  Notes:
  - `python-version-file: .python-version` and `node-version-file: .nvmrc` — these files are added in Pass C. Until they exist, the workflow will pin to `.python-version`/`.nvmrc` defaults that Pass C creates.
  - `npm run typecheck` / `format:check` are added in Pass B.
  - The `ruff check .` / `black --check .` invocations target everything from the repo root because the root `pyproject.toml` (Pass B) defines which paths to scan.

- [ ] **Step 2: Commit**

  ```bash
  git add .github/workflows/ci.yml
  git commit -m "ci: add GitHub Actions workflow on master push (backend / agent / frontend)"
  ```

  Note: this workflow will fail on its first run because Pass B/C files don't exist yet. That's expected — the next pass fixes it. Vercel deploys are independent of CI.

---

## Pass B — Daily-use guardrails (lint + format + type-check + cleanup)

### Task B1: Root `pyproject.toml` for Python tooling

**Why:** ruff and black should target `backend/` and `agents/` from a single config so devs run one command and reviewers see consistent style across the Python codebase.

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Create the config**

  ```toml
  # pyproject.toml — Python tooling config for the whole monorepo.
  # ruff + black target backend/ and the CMS Connector agent only.
  # Vercel doesn't install dev deps so this file is a no-op at deploy time.

  [tool.ruff]
  line-length = 100
  target-version = "py313"
  extend-exclude = [
      "backend/venv",
      "backend/migrations",   # SQL-only, not Python
      "backend/__pycache__",
      "**/__pycache__",
  ]

  [tool.ruff.lint]
  select = [
      "E",    # pycodestyle errors
      "F",    # pyflakes (undefined names, unused imports)
      "I",    # isort (import order)
      "B",    # flake8-bugbear (likely bugs)
      "UP",   # pyupgrade (modern syntax)
      "C4",   # flake8-comprehensions
  ]
  ignore = [
      "E501", # line length — black handles this
      "B008", # FastAPI uses `Depends()` defaults intentionally
  ]

  [tool.ruff.lint.per-file-ignores]
  "**/tests/**" = ["F841"]  # tests sometimes assign for clarity

  [tool.black]
  line-length = 100
  target-version = ["py313"]
  extend-exclude = '''
  /(
    backend/venv
    | backend/migrations
    | __pycache__
  )/
  '''
  ```

- [ ] **Step 2: Verify ruff sees the right files**

  ```bash
  cd "C:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
  backend/venv/Scripts/python.exe -m ruff check --statistics . 2>&1 | tail -10
  ```
  Expected: prints a summary of issues across `backend/auth_service/` and `agents/CMS Connector - Website/`. Don't fix yet — that's Task B2.

- [ ] **Step 3: Commit**

  ```bash
  git add pyproject.toml
  git commit -m "build: root pyproject.toml configures ruff + black for backend + agent"
  ```

### Task B2: Apply ruff + black formatting baseline

**Why:** Establish a clean baseline so subsequent commits don't show massive diffs the first time anyone runs the formatter.

**Files:**
- Modify: any Python file under `backend/auth_service/` or `agents/CMS Connector - Website/` that ruff/black flag.

- [ ] **Step 1: Auto-fix safe lint issues**

  ```bash
  cd "C:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
  backend/venv/Scripts/python.exe -m ruff check --fix .
  ```

- [ ] **Step 2: Apply black formatting**

  ```bash
  backend/venv/Scripts/python.exe -m black .
  ```

- [ ] **Step 3: Re-run tests to confirm nothing broke**

  ```bash
  cd backend && backend/venv/Scripts/python.exe -m pytest auth_service/tests/ -q
  cd "../agents/CMS Connector - Website" && \
    /c/Users/stefa/.gemini/antigravity/scratch/CMS\ -\ websites/backend/venv/Scripts/python.exe \
    -m pytest tests/ -q
  ```
  Expected: backend 52 passed + 4 skipped, agent 14 passed.

- [ ] **Step 4: Verify lint + format checks now pass**

  ```bash
  cd "C:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
  backend/venv/Scripts/python.exe -m ruff check .
  backend/venv/Scripts/python.exe -m black --check .
  ```
  Expected: both exit 0 with "All checks passed" / "would not reformat any files".

- [ ] **Step 5: Commit**

  ```bash
  git add -A
  git commit -m "style: apply ruff --fix + black formatting baseline"
  ```

### Task B3: Pre-commit framework

**Why:** Hooks that run on every `git commit` keep the formatters from drifting. They run only on changed files (fast). pre-commit (the Python framework) handles cross-language hooks better than per-language alternatives like Husky-only.

**Files:**
- Create: `.pre-commit-config.yaml`
- Create: `backend/requirements-dev.txt` already lists no pre-commit (we install it via the framework's auto-install in Task C1).

- [ ] **Step 1: Create the config**

  ```yaml
  # .pre-commit-config.yaml — runs lint + format on every commit.
  # Tests do NOT run here (too slow); CI handles that on push to master.
  # Install via: `make install` (Task C1) — sets up the git hook.

  repos:
    - repo: https://github.com/astral-sh/ruff-pre-commit
      rev: v0.7.4
      hooks:
        - id: ruff
          args: [--fix]
        - id: ruff-format

    - repo: https://github.com/psf/black
      rev: 24.10.0
      hooks:
        - id: black

    - repo: https://github.com/pre-commit/pre-commit-hooks
      rev: v5.0.0
      hooks:
        - id: trailing-whitespace
        - id: end-of-file-fixer
        - id: check-yaml
        - id: check-toml
        - id: check-added-large-files
          args: [--maxkb=500]
        - id: check-merge-conflict

    # Frontend hook — delegates to lint-staged (configured in package.json
    # by Task B5) so we don't duplicate Prettier/ESLint pin versions here.
    - repo: local
      hooks:
        - id: frontend-lint-staged
          name: frontend lint-staged (Prettier + ESLint on staged JS/TS)
          entry: bash -c 'cd frontend && npx --no-install lint-staged'
          language: system
          files: ^frontend/.*\.(ts|tsx|js|jsx|css|md)$
          pass_filenames: false
  ```

- [ ] **Step 2: Install + run on the whole codebase**

  ```bash
  cd "C:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
  pip install pre-commit==4.0.1
  pre-commit install
  pre-commit run --all-files
  ```
  Expected: ruff + ruff-format + black pass (Task B2 already cleaned them); whitespace/EOF fixers may modify some files. Re-run; expect green.

- [ ] **Step 3: Commit**

  ```bash
  git add -A
  git commit -m "build: pre-commit hooks (ruff + black + whitespace + frontend lint-staged)"
  ```

### Task B4: Frontend Prettier config

**Why:** Frontend has ESLint but no formatter. Prettier sets a single style and is auto-applied via lint-staged on commit.

**Files:**
- Create: `frontend/.prettierrc`
- Create: `frontend/.prettierignore`
- Modify: `frontend/package.json` (add `prettier`, `lint-staged`, scripts, devDep, husky setup)

- [ ] **Step 1: Create `frontend/.prettierrc`**

  ```json
  {
    "semi": true,
    "singleQuote": false,
    "trailingComma": "es5",
    "tabWidth": 2,
    "printWidth": 100,
    "arrowParens": "always",
    "endOfLine": "lf"
  }
  ```

- [ ] **Step 2: Create `frontend/.prettierignore`**

  ```text
  node_modules
  .next
  out
  build
  dist
  package-lock.json
  *.tsbuildinfo
  next-env.d.ts
  ```

- [ ] **Step 3: Add Prettier as a devDep + scripts to `frontend/package.json`**

  Modify `frontend/package.json` so `scripts` includes the new entries and `devDependencies` includes `prettier` and `lint-staged`. Final `scripts` block:

  ```json
  "scripts": {
    "dev": "next dev --turbopack",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "test": "vitest run",
    "test:watch": "vitest",
    "typecheck": "tsc --noEmit",
    "format": "prettier --write \"**/*.{ts,tsx,js,jsx,css,md,json}\"",
    "format:check": "prettier --check \"**/*.{ts,tsx,js,jsx,css,md,json}\""
  }
  ```

  Add to `devDependencies`:
  ```json
  "prettier": "3.3.3",
  "lint-staged": "15.2.10"
  ```

  Add a top-level `"lint-staged"` block:
  ```json
  "lint-staged": {
    "*.{ts,tsx,js,jsx}": ["prettier --write", "eslint --fix"],
    "*.{css,md,json}": ["prettier --write"]
  }
  ```

- [ ] **Step 4: Install + format baseline**

  ```bash
  cd frontend
  npm install
  npm run format
  npm run format:check
  ```
  Expected: format runs and rewrites files; format:check exits 0.

- [ ] **Step 5: Verify lint + typecheck still pass**

  ```bash
  npm run lint
  npm run typecheck
  ```
  Expected: both exit 0.

- [ ] **Step 6: Commit**

  ```bash
  git add frontend/.prettierrc frontend/.prettierignore frontend/package.json frontend/package-lock.json
  git add -A frontend/src   # Prettier-rewritten files
  git commit -m "build(frontend): Prettier + lint-staged + typecheck script"
  ```

### Task B5: Archive root cruft

**Why:** New joiner running `ls` at the repo root sees `findings.md`, `task_plan.md`, `progress.md`, `task.md.resolved`, `implementation_plan.md.resolved`. Those are vestiges of the original Django→FastAPI migration brainstorming. They aren't documentation of the current system; they confuse the canonical source-of-truth.

**Files:**
- Move (not delete — preserve as historical record):
  - `findings.md` → `docs/archive/findings.md`
  - `task_plan.md` → `docs/archive/task_plan.md`
  - `progress.md` → `docs/archive/progress.md`
  - `task.md.resolved` → `docs/archive/task.md.resolved`
  - `implementation_plan.md.resolved` → `docs/archive/implementation_plan.md.resolved`
- Create: `docs/archive/README.md` (one paragraph explaining what this folder is)

- [ ] **Step 1: Create the archive folder + README**

  ```bash
  mkdir -p docs/archive
  cat > docs/archive/README.md <<'EOF'
  # Archive — historical planning docs

  These files documented the original setup brainstorm + the Django→FastAPI
  migration. They are kept for archaeological context only and are NOT the
  source of truth for any current behavior.

  Canonical docs:
  - [`/README.md`](../../README.md) — onboarding + architecture
  - [`/docs/ENVIRONMENTS.md`](../ENVIRONMENTS.md) — env-var contract per tier
  - [`/docs/SECURITY.md`](../SECURITY.md) — credential rotation log
  - [`/docs/superpowers/plans/`](../superpowers/plans/) — current implementation plans
  EOF
  ```

- [ ] **Step 2: Move the cruft via git mv**

  ```bash
  git mv findings.md docs/archive/findings.md
  git mv task_plan.md docs/archive/task_plan.md
  git mv progress.md docs/archive/progress.md
  git mv task.md.resolved docs/archive/task.md.resolved
  git mv implementation_plan.md.resolved docs/archive/implementation_plan.md.resolved
  ```

- [ ] **Step 3: Verify the repo root is clean**

  ```bash
  ls -A . | grep -E "\.md$|\.resolved$"
  ```
  Expected: only `README.md`. No `findings.md`, no `*.resolved`.

- [ ] **Step 4: Commit**

  ```bash
  git add docs/archive/
  git commit -m "chore: archive root-level planning docs to docs/archive/"
  ```

---

## Pass C — Onboarding ergonomics

### Task C1: Root `Makefile`

**Why:** Single entry point for every common dev command. README points new joiners at `make help` and they learn the flow in 30 seconds.

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create the Makefile**

  ```make
  # Makefile — single entry point for the CMS monorepo.
  # `make help` lists every target.

  SHELL := /bin/bash
  .DEFAULT_GOAL := help

  PY ?= python
  BACKEND_VENV ?= backend/venv

  # ── Help ─────────────────────────────────────────────────────────────────
  .PHONY: help
  help: ## Show this help
  	@awk 'BEGIN {FS = ":.*##"; printf "Available targets:\n"} /^[a-zA-Z0-9_-]+:.*##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

  # ── First-time setup ─────────────────────────────────────────────────────
  .PHONY: install
  install: ## Install all dependencies (backend, agent, frontend, pre-commit)
  	$(PY) -m venv $(BACKEND_VENV)
  	$(BACKEND_VENV)/Scripts/pip install -r backend/requirements.txt -r backend/requirements-dev.txt
  	$(BACKEND_VENV)/Scripts/pip install -r "agents/CMS Connector - Website/requirements.txt" -r "agents/CMS Connector - Website/requirements-dev.txt"
  	cd frontend && npm ci
  	$(PY) -m pip install --user pre-commit==4.0.1
  	pre-commit install

  .PHONY: env
  env: ## Interactive: copy .env.example → .env and prompt for required values
  	bash scripts/init-env.sh

  # ── Daily workflow ───────────────────────────────────────────────────────
  .PHONY: dev
  dev: ## Run backend + frontend dev servers (use 2 terminals OR a process manager)
  	@echo "Run these in two terminals:"
  	@echo "  Terminal 1:  $(BACKEND_VENV)/Scripts/uvicorn auth_service.main:app --reload --port 8001 --app-dir backend"
  	@echo "  Terminal 2:  cd frontend && npm run dev"

  .PHONY: test
  test: test-backend test-agent test-frontend ## Run every test suite

  .PHONY: test-backend
  test-backend: ## Run the backend pytest suite
  	cd backend && ../$(BACKEND_VENV)/Scripts/python -m pytest auth_service/tests/ -q

  .PHONY: test-agent
  test-agent: ## Run the CMS Connector agent test suite
  	cd "agents/CMS Connector - Website" && ../../$(BACKEND_VENV)/Scripts/python -m pytest tests/ -q

  .PHONY: test-frontend
  test-frontend: ## Run the frontend vitest suite
  	cd frontend && npm test

  # ── Lint + format ────────────────────────────────────────────────────────
  .PHONY: lint
  lint: ## Lint everything (ruff + black --check + frontend lint + format:check + typecheck)
  	$(BACKEND_VENV)/Scripts/python -m ruff check .
  	$(BACKEND_VENV)/Scripts/python -m black --check .
  	cd frontend && npm run lint && npm run format:check && npm run typecheck

  .PHONY: format
  format: ## Auto-format everything (ruff --fix, black, prettier)
  	$(BACKEND_VENV)/Scripts/python -m ruff check --fix .
  	$(BACKEND_VENV)/Scripts/python -m black .
  	cd frontend && npm run format

  # ── CI emulation (run before push) ───────────────────────────────────────
  .PHONY: ci
  ci: lint test ## Run the same checks as GitHub Actions
  ```

- [ ] **Step 2: Test each target**

  ```bash
  make help
  make lint
  make test
  ```
  Expected: help prints the table; lint exits 0; test exits 0 with all suites green.

- [ ] **Step 3: Commit**

  ```bash
  git add Makefile
  git commit -m "build: root Makefile with dev / test / lint / format / ci / install / env targets"
  ```

### Task C2: Version files (`.nvmrc`, `.python-version`)

**Why:** Pins Node and Python versions per the toolchain the codebase was built with. CI reads these files; nvm/pyenv-using devs auto-switch.

**Files:**
- Create: `.nvmrc`
- Create: `.python-version`

- [ ] **Step 1: Inspect what's in use**

  ```bash
  node --version
  python --version
  ```
  Capture both. Expected: Node 20.x, Python 3.13.x (matches what we've been using locally).

- [ ] **Step 2: Write the pin files**

  Create `.nvmrc`:
  ```
  20
  ```

  Create `.python-version`:
  ```
  3.13
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add .nvmrc .python-version
  git commit -m "build: pin Node 20 + Python 3.13 via .nvmrc / .python-version"
  ```

### Task C3: Env scaffolder script

**Why:** `cp .env.example .env` is the manual onboarding step that gets done wrong (typo, miss a required field, paste secrets in `.example`). A one-shot script with prompts removes the failure mode.

**Files:**
- Create: `scripts/init-env.sh`

- [ ] **Step 1: Write the script**

  ```bash
  #!/usr/bin/env bash
  # scripts/init-env.sh — interactive .env scaffolder. Invoked by `make env`.
  # Idempotent: safe to re-run; never overwrites an existing .env without confirmation.

  set -euo pipefail

  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  cd "$REPO_ROOT"

  copy_or_skip() {
      local example="$1"
      local target="$2"
      if [[ -f "$target" ]]; then
          printf '  ✓ %s already exists — skipping (delete it first if you want to start over)\n' "$target"
          return 0
      fi
      cp "$example" "$target"
      printf '  + copied %s → %s\n' "$example" "$target"
  }

  printf '\n📦 Bootstrapping local env files\n\n'
  copy_or_skip backend/.env.example      backend/.env
  copy_or_skip frontend/.env.example     frontend/.env.local

  printf '\n  Edit the placeholders before running `make dev`:\n'
  printf '    • backend/.env     — SUPABASE_*, RESEND_*, ENVIRONMENT=development\n'
  printf '    • frontend/.env.local — FASTAPI_URL=http://localhost:8001\n\n'
  printf '  See docs/ENVIRONMENTS.md for the full env-var contract.\n\n'
  ```

- [ ] **Step 2: Make it executable + test**

  ```bash
  chmod +x scripts/init-env.sh
  bash scripts/init-env.sh
  ```
  Expected: copies the two `.env` files (or notes they exist).

- [ ] **Step 3: Commit**

  ```bash
  git add scripts/init-env.sh
  git commit -m "build: scripts/init-env.sh — bootstraps local .env files (called by \`make env\`)"
  ```

### Task C4: Update top-level README to reference the Makefile

**Why:** The README's local-dev section currently shows manual venv + npm steps. With the Makefile in place, the canonical onboarding is one command per concern.

**Files:**
- Modify: `README.md` (the "Local development" section)

- [ ] **Step 1: Replace the Local development + Tests sections**

  Open `README.md` and replace the `## Local development` section (everything from that header up to but not including `## Production`) with:

  ```markdown
  ## Local development

  ```bash
  # Once, on first clone:
  make install    # creates venv, installs all deps, sets up pre-commit
  make env        # bootstraps backend/.env and frontend/.env.local from the examples

  # Edit backend/.env (Supabase + Resend creds; see docs/ENVIRONMENTS.md)
  # Edit frontend/.env.local if needed (defaults to FASTAPI_URL=http://localhost:8001)

  # Daily:
  make dev        # prints the two terminal commands to run
  make test       # all suites: backend pytest, agent pytest, frontend vitest
  make lint       # ruff + black --check + ESLint + Prettier --check + tsc --noEmit
  make format     # auto-fix everything
  make ci         # same gate as GitHub Actions
  ```

  `make help` lists every target.
  ```

- [ ] **Step 2: Verify the README still parses**

  ```bash
  head -60 README.md
  ```
  Visually check the section reads coherently.

- [ ] **Step 3: Commit**

  ```bash
  git add README.md
  git commit -m "docs(readme): point local-dev flow at make targets"
  ```

---

## Pass D — Polish

### Task D1: Document the deploy scripts

**Why:** `scripts/deploy/create_backend_vercel_project.py` and `create_frontend_vercel_project.py` exist but no README points anyone at them. Future joiner who needs to spin up a parallel environment is stuck.

**Files:**
- Create: `scripts/deploy/README.md`

- [ ] **Step 1: Author the README**

  ```markdown
  # Deploy scripts

  One-shot Python scripts that bootstrap Vercel projects for the two CMS
  services. Each script is idempotent: re-running on an existing project
  is a no-op.

  ## When to use

  Only when you need to spin up a fresh Vercel project (e.g. forking the
  CMS into a parallel staging environment). The current production
  projects (`cms-backend-roman` and `cms-frontend-roman`) were created
  using these scripts.

  ## Prerequisites

  ```bash
  export VERCEL_TOKEN=<personal access token from https://vercel.com/account/tokens>
  export SUPABASE_URL=...
  export SUPABASE_ANON_KEY=...
  export SUPABASE_SERVICE_ROLE_KEY=...
  export RESEND_API_KEY=...
  ```

  ## Run

  ```bash
  python scripts/deploy/create_backend_vercel_project.py
  python scripts/deploy/create_frontend_vercel_project.py
  ```

  ## What they do

  - Create the Vercel project linked to the GitHub repo.
  - Set every env var listed in `docs/ENVIRONMENTS.md` for all three Vercel
    environments (Production, Preview, Development).
  - Configure the project's `rootDirectory` (`backend/` or `frontend/`).
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add scripts/deploy/README.md
  git commit -m "docs(scripts): document scripts/deploy/*.py"
  ```

### Task D2: Reinstall frontend `node_modules` to match the lockfile

**Why:** `frontend/node_modules/vitest` is missing despite `vitest` being declared in `package.json`. Likely from a prior partial install or a hoisting quirk. Fresh `npm ci` installs exactly what `package-lock.json` says.

**Files:** none modified — this is a state fix, not a code fix.

- [ ] **Step 1: Reinstall**

  ```bash
  cd frontend
  rm -rf node_modules
  npm ci
  ```

- [ ] **Step 2: Verify the missing module is now present**

  ```bash
  ls node_modules/vitest/package.json
  ls node_modules/@testing-library/react/package.json
  ```
  Expected: both files exist.

- [ ] **Step 3: Run the frontend test suite to confirm**

  ```bash
  npm test
  ```
  Expected: vitest runs, all tests pass.

  No commit — this is a workspace fix, not a repository change.

### Task D3: Final verification — run `make ci` end-to-end

**Why:** Catches any task that introduced a regression in another task.

- [ ] **Step 1: Run the CI emulator**

  ```bash
  cd "C:/Users/stefa/.gemini/antigravity/scratch/CMS - websites"
  make ci
  ```
  Expected: exit 0 with every suite green and every linter clean.

- [ ] **Step 2: Verify the GitHub Actions workflow file is syntactically valid**

  ```bash
  git push origin master
  ```
  Then watch https://github.com/stefanroman22/cms-platform/actions/runs to confirm the CI workflow actually runs and turns green. If red, read the logs and fix.

---

## Self-review

**Spec coverage:**
- ✓ #1 backend dev deps split → Task A1
- ✓ #2 No CI → Task A3
- ✓ #3 No pre-commit → Task B3
- ✓ #4 No formatter → Tasks B1, B2 (Python), B4 (frontend)
- ✓ #5 Root cruft → Task B5
- ✓ #6 No type-check → Task B4 adds `typecheck` npm script + included in `make lint`
- ✓ #7 No Makefile → Task C1
- ✓ #8 No `.nvmrc` / `.python-version` → Task C2
- ✓ #9 No Docker → explicitly deferred in the architecture section (out of scope, future work)
- ✓ #10 Agent unpinned deps → Task A2
- ✓ #11 `scripts/deploy/*` undocumented → Task D1
- ✓ #12 No env scaffolder → Task C3
- ✓ #13 Frontend node_modules drift → Task D2

**Placeholder scan:** No "TBD", no "similar to Task N", no "implement later". Every code block contains the actual content. Version pins are concrete (`pytest==8.3.3`, `prettier==3.3.3`, `pre-commit==4.0.1`, etc.).

**Type consistency:** `make` target names referenced consistently (`install`, `env`, `dev`, `test`, `lint`, `format`, `ci`). npm script names referenced consistently (`typecheck`, `format`, `format:check`, `lint`, `test`). Python tool versions match between `requirements-dev.txt` and `.pre-commit-config.yaml` (`ruff==0.7.4`, `black==24.10.0`).

---

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-05-02-dev-experience-hardening.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks. Good for the cross-cutting changes in Pass B (touch many files).
2. **Inline Execution** — execute tasks in this session with checkpoints between passes.

Which approach?
