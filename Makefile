.PHONY: setup setup-dev test lint format run run-full _run-dry clean

PYTHON := .venv/bin/python
PIP := .venv/bin/pip

setup:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e .

setup-dev: setup
	$(PIP) install -e ".[dev]"

test:
	PYTHONPATH=. $(PYTHON) -m unittest discover -s tests -p "test_*.py"

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
#   make run-full
#   make run REPO=owner/repo PR=123 TOKEN=ghp_... [KEY=...]
run: DRY_RUN_OUTPUT=summary
run: _run-dry

run-full: DRY_RUN_OUTPUT=full
run-full: _run-dry

_run-dry:
	@set -a; \
	if [ -f .env ]; then . ./.env; fi; \
	set +a; \
	REPO_VAL="$(REPO)"; \
	PR_VAL="$(PR)"; \
	TOKEN_VAL="$(TOKEN)"; \
	KEY_VAL="$(KEY)"; \
	OUTPUT_MODE_VAL="$(DRY_RUN_OUTPUT)"; \
	if [ -z "$$REPO_VAL" ]; then REPO_VAL="$$GITHUB_REPOSITORY"; fi; \
	if [ -z "$$PR_VAL" ]; then PR_VAL="$$PR_NUMBER"; fi; \
	if [ -z "$$TOKEN_VAL" ]; then TOKEN_VAL="$$GITHUB_TOKEN"; fi; \
	if [ -z "$$KEY_VAL" ]; then KEY_VAL="$$GEMINI_API_KEY"; fi; \
	if [ -z "$$KEY_VAL" ]; then KEY_VAL="$$OPENAI_API_KEY"; fi; \
	if [ -z "$$OUTPUT_MODE_VAL" ]; then OUTPUT_MODE_VAL="summary"; fi; \
	if [ -n "$$KEY_VAL" ]; then \
		export GEMINI_API_KEY="$$KEY_VAL"; \
		export OPENAI_API_KEY="$$KEY_VAL"; \
	fi; \
	if [ -z "$$REPO_VAL" ] || [ -z "$$PR_VAL" ] || [ -z "$$TOKEN_VAL" ]; then \
		echo "Error: missing required values (REPO, PR, TOKEN)."; \
		echo "Fill .env or run: make run REPO=owner/repo PR=123 TOKEN=ghp_... [KEY=...]"; \
		exit 1; \
	fi; \
	GITHUB_TOKEN="$$TOKEN_VAL" $(PYTHON) -m src.main review --repo "$$REPO_VAL" --pr "$$PR_VAL" --dry-run --dry-run-output "$$OUTPUT_MODE_VAL"
