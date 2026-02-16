import unittest

from src.safety.utils import SafeJSONParser, SecretRedactor


class TestSecretRedactor(unittest.TestCase):
    def setUp(self) -> None:
        self.redactor = SecretRedactor()

    def test_redacts_literal_secret_assignments(self) -> None:
        text = (
            'password = "supersecret123"\n'
            'passwrod = "typo_secret_123"\n'
            'api_key: "abcDEF1234567890"'
        )
        redacted = self.redactor.redact(text)

        self.assertNotIn("supersecret123", redacted)
        self.assertNotIn("typo_secret_123", redacted)
        self.assertNotIn("abcDEF1234567890", redacted)
        self.assertIn("password", redacted)
        self.assertIn("passwrod", redacted)
        self.assertIn("api_key", redacted)
        self.assertIn("********", redacted)

    def test_does_not_redact_regular_auth_code_references(self) -> None:
        text = "auth = authenticate_user(user, password)\nkey = derive_key(material)"
        redacted = self.redactor.redact(text)

        self.assertEqual(redacted, text)

    def test_redacts_known_token_formats(self) -> None:
        token = "ghp_" + "a" * 36
        hf_token = "hf_" + "A" * 34
        openai_key = "sk-" + "A" * 30
        gemini_key = "AIza" + "A" * 35
        text = f"{token}\n{hf_token}\n{openai_key}\n{gemini_key}"

        redacted = self.redactor.redact(text)

        self.assertNotIn(token, redacted)
        self.assertNotIn(hf_token, redacted)
        self.assertNotIn(openai_key, redacted)
        self.assertNotIn(gemini_key, redacted)
        self.assertIn("********", redacted)


class TestSafeJSONParser(unittest.TestCase):
    def test_cleans_trailing_fence_even_without_opening(self) -> None:
        raw = '{"key":"value"}\n```'
        cleaned = SafeJSONParser.clean_json_text(raw)
        self.assertEqual(cleaned, '{"key":"value"}')

    def test_cleans_json_wrapped_with_text_and_fences(self) -> None:
        raw = (
            "Here is JSON:\n"
            "```json\n"
            '{"issues":[{"id":"a","line_start":2}]}\n'
            "```\n"
            "End."
        )
        cleaned = SafeJSONParser.clean_json_text(raw)
        self.assertEqual(cleaned, '{"issues":[{"id":"a","line_start":2}]}')


if __name__ == "__main__":
    unittest.main()
