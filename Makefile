.PHONY: setup setup-dev test lint format run run-full run-hf run-hf-full run-ollama run-ollama-full ollama-pull ollama-serve _run-dry clean

PYTHON := .venv/bin/python
PIP := .venv/bin/pip
HF_BASE_URL_DEFAULT := https://router.huggingface.co/v1
HF_MODEL_DEFAULT := Qwen/Qwen2.5-Coder-32B-Instruct
OLLAMA_BASE_URL_DEFAULT := http://127.0.0.1:11434/v1
OLLAMA_MODEL_DEFAULT := qwen2.5-coder:7b

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
#   make run-hf
#   make run-hf-full
#   make run-ollama
#   make run-ollama-full
#   make run REPO=owner/repo PR=123 TOKEN=ghp_... [KEY=...]
run: DRY_RUN_OUTPUT=summary
run: _run-dry

run-full: DRY_RUN_OUTPUT=full
run-full: _run-dry

run-hf: DRY_RUN_OUTPUT=summary
run-hf: LLM_PROVIDER_OVERRIDE=huggingface
run-hf: LLM_MODEL_OVERRIDE=$(HF_MODEL_DEFAULT)
run-hf: LLM_BASE_URL_OVERRIDE=$(HF_BASE_URL_DEFAULT)
run-hf: _run-dry

run-hf-full: DRY_RUN_OUTPUT=full
run-hf-full: LLM_PROVIDER_OVERRIDE=huggingface
run-hf-full: LLM_MODEL_OVERRIDE=$(HF_MODEL_DEFAULT)
run-hf-full: LLM_BASE_URL_OVERRIDE=$(HF_BASE_URL_DEFAULT)
run-hf-full: _run-dry

run-ollama: DRY_RUN_OUTPUT=summary
run-ollama: LLM_PROVIDER_OVERRIDE=ollama
run-ollama: LLM_MODEL_OVERRIDE=$(OLLAMA_MODEL_DEFAULT)
run-ollama: LLM_BASE_URL_OVERRIDE=$(OLLAMA_BASE_URL_DEFAULT)
run-ollama: _run-dry

run-ollama-full: DRY_RUN_OUTPUT=full
run-ollama-full: LLM_PROVIDER_OVERRIDE=ollama
run-ollama-full: LLM_MODEL_OVERRIDE=$(OLLAMA_MODEL_DEFAULT)
run-ollama-full: LLM_BASE_URL_OVERRIDE=$(OLLAMA_BASE_URL_DEFAULT)
run-ollama-full: _run-dry

ollama-pull:
	@if ! command -v ollama >/dev/null 2>&1; then \
		echo "Error: ollama not found."; \
		echo "Install it with: brew install ollama"; \
		exit 1; \
	fi
	ollama pull $(OLLAMA_MODEL_DEFAULT)

ollama-serve:
	@if ! command -v ollama >/dev/null 2>&1; then \
		echo "Error: ollama not found."; \
		echo "Install it with: brew install ollama"; \
		exit 1; \
	fi
	ollama serve

_run-dry:
	@set -a; \
	if [ -f .env ]; then . ./.env; fi; \
	set +a; \
	REPO_VAL="$(REPO)"; \
	PR_VAL="$(PR)"; \
	TOKEN_VAL="$(TOKEN)"; \
	KEY_VAL="$(KEY)"; \
	OUTPUT_MODE_VAL="$(DRY_RUN_OUTPUT)"; \
	PROVIDER_VAL="$(LLM_PROVIDER_OVERRIDE)"; \
	MODEL_VAL="$(LLM_MODEL_OVERRIDE)"; \
	BASE_URL_VAL="$(LLM_BASE_URL_OVERRIDE)"; \
	if [ -z "$$REPO_VAL" ]; then REPO_VAL="$$GITHUB_REPOSITORY"; fi; \
	if [ -z "$$PR_VAL" ]; then PR_VAL="$$PR_NUMBER"; fi; \
	if [ -z "$$TOKEN_VAL" ]; then TOKEN_VAL="$$GITHUB_TOKEN"; fi; \
	if [ -z "$$PROVIDER_VAL" ]; then PROVIDER_VAL="$$LLM_PROVIDER"; fi; \
	if [ -z "$$MODEL_VAL" ]; then MODEL_VAL="$$LLM_MODEL"; fi; \
	if [ -z "$$BASE_URL_VAL" ]; then BASE_URL_VAL="$$LLM_BASE_URL"; fi; \
	if [ -z "$$KEY_VAL" ]; then \
		case "$$PROVIDER_VAL" in \
			huggingface|hf) KEY_VAL="$$HF_TOKEN"; [ -z "$$KEY_VAL" ] && KEY_VAL="$$HUGGINGFACE_API_KEY"; [ -z "$$KEY_VAL" ] && KEY_VAL="$$OPENAI_API_KEY" ;; \
			gemini) KEY_VAL="$$GEMINI_API_KEY"; [ -z "$$KEY_VAL" ] && KEY_VAL="$$OPENAI_API_KEY" ;; \
			openai) KEY_VAL="$$OPENAI_API_KEY" ;; \
			ollama) KEY_VAL="$$OLLAMA_API_KEY"; [ -z "$$KEY_VAL" ] && KEY_VAL="$$OPENAI_API_KEY"; [ -z "$$KEY_VAL" ] && KEY_VAL="dummy" ;; \
			vllm) KEY_VAL="$$VLLM_API_KEY"; [ -z "$$KEY_VAL" ] && KEY_VAL="$$OPENAI_API_KEY"; [ -z "$$KEY_VAL" ] && KEY_VAL="dummy" ;; \
			*) KEY_VAL="$$HF_TOKEN"; [ -z "$$KEY_VAL" ] && KEY_VAL="$$HUGGINGFACE_API_KEY"; [ -z "$$KEY_VAL" ] && KEY_VAL="$$GEMINI_API_KEY"; [ -z "$$KEY_VAL" ] && KEY_VAL="$$OPENAI_API_KEY"; [ -z "$$KEY_VAL" ] && KEY_VAL="$$OLLAMA_API_KEY" ;; \
		esac; \
	fi; \
	if [ -z "$$OUTPUT_MODE_VAL" ]; then OUTPUT_MODE_VAL="summary"; fi; \
	if [ -n "$$PROVIDER_VAL" ]; then export LLM_PROVIDER="$$PROVIDER_VAL"; fi; \
	if [ -n "$$MODEL_VAL" ]; then export LLM_MODEL="$$MODEL_VAL"; fi; \
	if [ -n "$$BASE_URL_VAL" ]; then export LLM_BASE_URL="$$BASE_URL_VAL"; fi; \
	if [ -n "$$KEY_VAL" ]; then \
		export HF_TOKEN="$$KEY_VAL"; \
		export HUGGINGFACE_API_KEY="$$KEY_VAL"; \
		export GEMINI_API_KEY="$$KEY_VAL"; \
		export OPENAI_API_KEY="$$KEY_VAL"; \
		export OLLAMA_API_KEY="$$KEY_VAL"; \
		export VLLM_API_KEY="$$KEY_VAL"; \
	fi; \
	if [ -z "$$REPO_VAL" ] || [ -z "$$PR_VAL" ] || [ -z "$$TOKEN_VAL" ]; then \
		echo "Error: missing required values (REPO, PR, TOKEN)."; \
		echo "Fill .env or run: make run REPO=owner/repo PR=123 TOKEN=ghp_... [KEY=...]"; \
		exit 1; \
	fi; \
	GITHUB_TOKEN="$$TOKEN_VAL" $(PYTHON) -m src.main review --repo "$$REPO_VAL" --pr "$$PR_VAL" --dry-run --dry-run-output "$$OUTPUT_MODE_VAL"
