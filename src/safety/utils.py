import json
import logging
import re
from typing import Any


class SecretRedactor:
    """
    Redacts secrets from strings to prevent leakage in logs or comments.
    """

    # Patterns prioritize high-signal secrets and quoted literal assignments
    # to avoid over-redacting normal auth module code.
    PATTERNS = [
        # Generic secret-like assignment where literal value is explicitly present.
        r"""(?i)\b(api[_-]?key|token|secret|password|passwrod|passw(?:o|or)?rd|pwd|auth)\b\s*[:=]\s*(['"])([^'"\r\n]{8,})\2""",
        # GitHub fine-grained/classic tokens.
        r"(github_pat_[A-Za-z0-9_]{82})",
        r"(gh[opusr]_[A-Za-z0-9]{36})",
        # OpenAI-style keys (sk-..., including project-prefixed forms).
        r"\b(sk-[A-Za-z0-9_-]{20,})\b",
        # Google/Gemini API keys.
        r"\b(AIza[0-9A-Za-z\-_]{35})\b",
    ]

    def __init__(self):
        self.compiled_patterns = [re.compile(p) for p in self.PATTERNS]

    def redact(self, text: str) -> str:
        if not text:
            return text

        redacted = text
        for pattern in self.compiled_patterns:

            def replace_match(match: re.Match[str]) -> str:
                full_match = match.group(0)
                last_idx = match.lastindex
                if last_idx is None:
                    return "********"

                value = match.group(last_idx)
                return full_match.replace(value, "********")

            redacted = pattern.sub(replace_match, redacted)

        return redacted


class SafeJSONParser:
    """
    Robust JSON parser with repair capabilities.
    """

    @staticmethod
    def clean_json_text(text: str) -> str:
        """
        Return text cleaned from markdown code fences.
        """
        cleaned = text.strip()

        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        return cleaned

    @staticmethod
    def parse(text: str) -> dict[str, Any]:
        """
        Tries to parse JSON, cleaning markdown code blocks if present.
        """
        cleaned = SafeJSONParser.clean_json_text(text)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # TODO: Add more sophisticated repair (e.g. balancing braces) if needed
            logging.error(f"JSON Parse Error: {e}. Content: {cleaned[:100]}...")
            raise
