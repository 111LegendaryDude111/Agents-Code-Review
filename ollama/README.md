# Ollama Local Inference (Mac-friendly)

This profile is intended for local testing without CUDA/GPU requirements.

## 1) Install and start Ollama

```bash
brew install ollama
ollama serve
```

Run `ollama serve` in a separate terminal tab.

## 2) Pull a lightweight coder model

```bash
make ollama-pull
```

Default model in this project:

```text
qwen2.5-coder:7b
```

## 3) Run code review through Ollama

```bash
make run-ollama REPO=owner/repo PR=123 TOKEN=ghp_...
```

Full terminal output:

```bash
make run-ollama-full REPO=owner/repo PR=123 TOKEN=ghp_...
```
