.PHONY: setup setup-dev test lint format run clean

PYTHON := .venv/bin/python
PIP := .venv/bin/pip

setup:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e .

setup-dev: setup
	$(PIP) install -e ".[dev]"

test:
	PYTHONPATH=. $(PYTHON) tests/test_flow.py

lint:
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m black --check src tests

format:
	$(PYTHON) -m ruff check --fix src tests
	$(PYTHON) -m black src tests

clean:
	rm -rf .venv
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +

# Example run command (dry-run by default)
# Usage:
#   make run
#   make run REPO=owner/repo PR=123 TOKEN=ghp_... [KEY=...]
run:
	@set -a; \
	if [ -f .env ]; then . ./.env; fi; \
	set +a; \
	REPO_VAL="$(REPO)"; \
	PR_VAL="$(PR)"; \
	TOKEN_VAL="$(TOKEN)"; \
	KEY_VAL="$(KEY)"; \
	if [ -z "$$REPO_VAL" ]; then REPO_VAL="$$GITHUB_REPOSITORY"; fi; \
	if [ -z "$$PR_VAL" ]; then PR_VAL="$$PR_NUMBER"; fi; \
	if [ -z "$$TOKEN_VAL" ]; then TOKEN_VAL="$$GITHUB_TOKEN"; fi; \
	if [ -z "$$KEY_VAL" ]; then KEY_VAL="$$GEMINI_API_KEY"; fi; \
	if [ -z "$$KEY_VAL" ]; then KEY_VAL="$$OPENAI_API_KEY"; fi; \
	if [ -n "$$KEY_VAL" ]; then \
		export GEMINI_API_KEY="$$KEY_VAL"; \
		export OPENAI_API_KEY="$$KEY_VAL"; \
	fi; \
	if [ -z "$$REPO_VAL" ] || [ -z "$$PR_VAL" ] || [ -z "$$TOKEN_VAL" ]; then \
		echo "Error: missing required values (REPO, PR, TOKEN)."; \
		echo "Fill .env or run: make run REPO=owner/repo PR=123 TOKEN=ghp_... [KEY=...]"; \
		exit 1; \
	fi; \
	GITHUB_TOKEN="$$TOKEN_VAL" $(PYTHON) -m src.main review --repo "$$REPO_VAL" --pr "$$PR_VAL" --dry-run
