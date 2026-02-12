import os
import unittest
from unittest.mock import patch

from src.review.llm import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_VLLM_BASE_URL,
    DEFAULT_VLLM_MODEL,
    LLMClient,
)


class TestLLMClient(unittest.TestCase):
    @patch("src.review.llm.load_env_file", return_value=None)
    @patch("src.review.llm.openai.OpenAI")
    def test_vllm_defaults_to_qwen_and_local_url(
        self, mock_openai_client, _mock_load_env
    ):
        with patch.dict(os.environ, {"LLM_PROVIDER": "vllm"}, clear=True):
            client = LLMClient()

        mock_openai_client.assert_called_once_with(
            api_key="dummy",
            base_url=DEFAULT_VLLM_BASE_URL,
        )
        self.assertEqual(client.model, DEFAULT_VLLM_MODEL)

    @patch("src.review.llm.load_env_file", return_value=None)
    @patch("src.review.llm.openai.OpenAI")
    def test_vllm_uses_provider_specific_env(self, mock_openai_client, _mock_load_env):
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "vllm",
                "VLLM_API_KEY": "local-secret",
                "VLLM_BASE_URL": "http://localhost:9000/v1",
                "VLLM_MODEL": "Qwen/Qwen2.5-Coder-14B-Instruct",
            },
            clear=True,
        ):
            client = LLMClient()

        mock_openai_client.assert_called_once_with(
            api_key="local-secret",
            base_url="http://localhost:9000/v1",
        )
        self.assertEqual(client.model, "Qwen/Qwen2.5-Coder-14B-Instruct")

    @patch("src.review.llm.load_env_file", return_value=None)
    @patch("src.review.llm.openai.OpenAI")
    def test_ollama_defaults(self, mock_openai_client, _mock_load_env):
        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}, clear=True):
            client = LLMClient()

        mock_openai_client.assert_called_once_with(
            api_key="dummy",
            base_url=DEFAULT_OLLAMA_BASE_URL,
        )
        self.assertEqual(client.model, DEFAULT_OLLAMA_MODEL)


if __name__ == "__main__":
    unittest.main()
