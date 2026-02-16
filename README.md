# AI Code Review

This project is a lightweight AI reviewer for pull requests in CI/CD.
It analyzes code diffs with an LLM, applies policy filters, and publishes concise review feedback to GitHub PRs.

The tool is designed to be advisory (non-blocking): it highlights risks, prioritizes important issues, and keeps comments synchronized across runs to avoid noise.

## Default LLM Backend

The default provider is Hugging Face Inference API (OpenAI-compatible endpoint).

## Hugging Face API Key

1. Create or sign in to your Hugging Face account.
2. Open `https://huggingface.co/settings/tokens`.
3. Create a token (read or fine-grained) and enable permission: `Make calls to Inference Providers`.
4. Configure the token:
   - Local: set `HF_TOKEN=hf_...` in `.env`
   - CI (GitHub Actions): add repository secret `HF_TOKEN`
