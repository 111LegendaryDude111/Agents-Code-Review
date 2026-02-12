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

        provider = (os.getenv("LLM_PROVIDER", "gemini")).strip().lower()
        default_model = "gemini-2.5-flash"
        resolved_base_url = base_url

        if provider == "gemini":
            resolved_api_key = (
                api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
            )
            if not resolved_base_url:
                resolved_base_url = (
                    os.getenv("LLM_BASE_URL")
                    or "https://generativelanguage.googleapis.com/v1beta/openai/"
                )
            default_model = "gemini-2.5-flash"
        else:
            resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
            # Optional override for OpenAI-compatible gateways.
            if not resolved_base_url:
                resolved_base_url = os.getenv("LLM_BASE_URL")
            default_model = "gpt-4o-mini"

        if not resolved_api_key:
            raise ValueError(
                "LLM API key is missing. Set GEMINI_API_KEY or OPENAI_API_KEY."
            )

        # Use explicit args to keep static type checkers happy.
        if resolved_base_url:
            self.client = openai.OpenAI(
                api_key=resolved_api_key,
                base_url=resolved_base_url,
            )
        else:
            self.client = openai.OpenAI(api_key=resolved_api_key)
        self.model = model or os.getenv("LLM_MODEL") or default_model

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
        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("LLM response is empty.")
        return content
