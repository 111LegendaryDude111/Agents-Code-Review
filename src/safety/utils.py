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
    COMPILED_PATTERNS = tuple(re.compile(pattern) for pattern in PATTERNS)

    def __init__(self):
        self.compiled_patterns = self.COMPILED_PATTERNS

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
    def _strip_markdown_fences(text: str) -> str:
        lines: list[str] = []
        for line in text.splitlines():
            if line.strip().startswith("```"):
                continue
            lines.append(line)
        return "\n".join(lines).strip()

    @staticmethod
    def _extract_first_json_payload(text: str) -> str:
        start_candidates = [idx for idx in (text.find("{"), text.find("[")) if idx >= 0]
        if not start_candidates:
            return text.strip()

        start_idx = min(start_candidates)
        payload = text[start_idx:]
        opening = payload[0]
        closing = "}" if opening == "{" else "]"

        depth = 0
        in_string = False
        is_escaped = False

        for index, char in enumerate(payload):
            if in_string:
                if is_escaped:
                    is_escaped = False
                    continue
                if char == "\\":
                    is_escaped = True
                    continue
                if char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
                continue

            if char == opening:
                depth += 1
                continue

            if char == closing:
                depth -= 1
                if depth == 0:
                    return payload[: index + 1].strip()

        return payload.strip()

    @staticmethod
    def clean_json_text(text: str) -> str:
        """
        Return text cleaned from markdown code fences.
        """
        base = text.strip()
        if not base:
            return ""

        no_fences = SafeJSONParser._strip_markdown_fences(base)
        return SafeJSONParser._extract_first_json_payload(no_fences)

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
            logging.error("JSON Parse Error: %s. Content: %s...", e, cleaned[:100])
            raise
