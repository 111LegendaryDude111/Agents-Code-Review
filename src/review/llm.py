import os
from typing import Any

import openai
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..safety.env_loader import load_env_file

DEFAULT_HUGGINGFACE_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"
DEFAULT_HUGGINGFACE_BASE_URL = "https://router.huggingface.co/v1"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OLLAMA_MODEL = "qwen2.5-coder:7b"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_VLLM_MODEL = "Qwen/Qwen2.5-Coder-14B-Instruct"
DEFAULT_VLLM_BASE_URL = "http://127.0.0.1:8000/v1"


def _first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if value is None:
            continue
        normalized = value.strip()
        if normalized:
            return normalized
    return None


def is_rate_limit_error(exc: BaseException) -> bool:
    if isinstance(exc, openai.RateLimitError):
        return True
    if isinstance(exc, RetryError):
        try:
            last_exc = exc.last_attempt.exception()
        except Exception:
            return False
        return isinstance(last_exc, openai.RateLimitError)
    return False


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        # Load .env values for local/dev usage.
        load_env_file(".env")

        provider = (os.getenv("LLM_PROVIDER", "huggingface")).strip().lower()
        if provider == "hf":
            provider = "huggingface"
        self.provider = provider
        resolved_base_url = _first_non_empty(base_url)
        provider_default_model: str
        provider_model_override: str | None = None

        if provider == "huggingface":
            resolved_api_key = _first_non_empty(
                api_key,
                os.getenv("HF_TOKEN"),
                os.getenv("HUGGINGFACE_API_KEY"),
                os.getenv("OPENAI_API_KEY"),
            )
            if not resolved_base_url:
                resolved_base_url = _first_non_empty(
                    os.getenv("HUGGINGFACE_BASE_URL"),
                    os.getenv("LLM_BASE_URL"),
                    DEFAULT_HUGGINGFACE_BASE_URL,
                )
            provider_default_model = DEFAULT_HUGGINGFACE_MODEL
            provider_model_override = _first_non_empty(
                os.getenv("HUGGINGFACE_MODEL"),
                os.getenv("HF_MODEL"),
            )
        elif provider == "gemini":
            resolved_api_key = _first_non_empty(
                api_key, os.getenv("GEMINI_API_KEY"), os.getenv("OPENAI_API_KEY")
            )
            if not resolved_base_url:
                resolved_base_url = _first_non_empty(
                    os.getenv("LLM_BASE_URL"), DEFAULT_GEMINI_BASE_URL
                )
            provider_default_model = DEFAULT_GEMINI_MODEL
        elif provider == "openai":
            resolved_api_key = _first_non_empty(api_key, os.getenv("OPENAI_API_KEY"))
            # Optional override for OpenAI-compatible gateways.
            if not resolved_base_url:
                resolved_base_url = _first_non_empty(os.getenv("LLM_BASE_URL"))
            provider_default_model = DEFAULT_OPENAI_MODEL
        elif provider == "ollama":
            resolved_api_key = _first_non_empty(
                api_key,
                os.getenv("OLLAMA_API_KEY"),
                os.getenv("OPENAI_API_KEY"),
                "dummy",
            )
            if not resolved_base_url:
                resolved_base_url = _first_non_empty(
                    os.getenv("OLLAMA_BASE_URL"),
                    os.getenv("LLM_BASE_URL"),
                    DEFAULT_OLLAMA_BASE_URL,
                )
            provider_default_model = DEFAULT_OLLAMA_MODEL
            provider_model_override = _first_non_empty(os.getenv("OLLAMA_MODEL"))
        elif provider == "vllm":
            resolved_api_key = _first_non_empty(
                api_key,
                os.getenv("VLLM_API_KEY"),
                os.getenv("OPENAI_API_KEY"),
                "dummy",
            )
            if not resolved_base_url:
                resolved_base_url = _first_non_empty(
                    os.getenv("VLLM_BASE_URL"),
                    os.getenv("LLM_BASE_URL"),
                    DEFAULT_VLLM_BASE_URL,
                )
            provider_default_model = DEFAULT_VLLM_MODEL
            provider_model_override = _first_non_empty(os.getenv("VLLM_MODEL"))
        else:
            raise ValueError(
                "Unsupported LLM_PROVIDER. Use one of: huggingface, gemini, openai, ollama, vllm."
            )

        if not resolved_api_key:
            raise ValueError(
                "LLM API key is missing. Set HF_TOKEN / HUGGINGFACE_API_KEY / GEMINI_API_KEY / OPENAI_API_KEY / OLLAMA_API_KEY / VLLM_API_KEY."
            )

        # Use explicit args to keep static type checkers happy.
        if resolved_base_url:
            self.client = openai.OpenAI(
                api_key=resolved_api_key,
                base_url=resolved_base_url,
            )
        else:
            self.client = openai.OpenAI(api_key=resolved_api_key)
        self.model = (
            _first_non_empty(model, os.getenv("LLM_MODEL"), provider_model_override)
            or provider_default_model
        )

    @retry(
        retry=retry_if_exception_type(
            (
                openai.RateLimitError,
                openai.APIConnectionError,
                openai.APITimeoutError,
                openai.InternalServerError,
            )
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    def get_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """
        Get completion from LLM.
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        # Ollama's OpenAI-compatible endpoint may not support json_object mode.
        if response_format and self.provider != "ollama":
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("LLM response is empty.")
        return content
