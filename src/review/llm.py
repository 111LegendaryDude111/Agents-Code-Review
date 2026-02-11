import os
from typing import Dict, Optional
import openai
from tenacity import retry, stop_after_attempt, wait_exponential
from ..safety.env_loader import load_env_file


class LLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        # Load .env values for local/dev usage.
        load_env_file(".env")

        provider = (os.getenv("LLM_PROVIDER", "gemini")).strip().lower()
        default_model = "gemini-2.5-flash"
        resolved_base_url = base_url

        if provider == "gemini":
            resolved_api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
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

        client_kwargs = {"api_key": resolved_api_key}
        if resolved_base_url:
            client_kwargs["base_url"] = resolved_base_url

        self.client = openai.OpenAI(**client_kwargs)
        self.model = model or os.getenv("LLM_MODEL") or default_model

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def get_completion(
        self, system_prompt: str, user_prompt: str, response_format: Dict = None
    ) -> str:
        """
        Get completion from LLM.
        """
        kwargs = {
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
        return response.choices[0].message.content
