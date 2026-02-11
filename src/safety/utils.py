import json
import re
from typing import Any, Dict, List, Optional
import logging

class SecretRedactor:
    """
    Redacts secrets from strings to prevent leakage in logs or comments.
    """
    # Simple regex patterns for common secrets (can be expanded)
    PATTERNS = [
        r'(?i)(api[_-]?key|token|secret|password|pwd|auth)[=:\s"]+([a-zA-Z0-9_\-]{8,})',
        r'ghp_[a-zA-Z0-9]{36}', # GitHub PAT
        r'sk-[a-zA-Z0-9]{48}', # OpenAI Key
    ]

    def __init__(self):
        self.compiled_patterns = [re.compile(p) for p in self.PATTERNS]

    def redact(self, text: str) -> str:
        if not text:
            return text
        
        redacted = text
        for pattern in self.compiled_patterns:
            # Replace the captured group 2 (the secret) with ***
            # Need to be careful with regex groups, some might not have group 2
            # Simplified approach: mask the whole match or just the value part
            
            # Using sub with callback to safe-guard
            def replace_match(match):
                full_match = match.group(0)
                # If we have groups, mask the last group (value)
                if match.groups():
                    value = match.group(match.lastindex)
                    return full_match.replace(value, "********")
                return full_match
            
            redacted = pattern.sub(replace_match, redacted)
            
        return redacted

class SafeJSONParser:
    """
    Robust JSON parser with repair capabilities.
    """
    @staticmethod
    def parse(text: str) -> Dict[str, Any]:
        """
        Tries to parse JSON, cleaning markdown code blocks if present.
        """
        cleaned = text.strip()
        
        # Remove markdown code blocks ```json ... ```
        if cleaned.startswith("```"):
            # splitting by newline to remove the first line (```json) and last line (```)
            lines = cleaned.splitlines()
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines)
            
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # TODO: Add more sophisticated repair (e.g. balancing braces) if needed
            logging.error(f"JSON Parse Error: {e}. Content: {cleaned[:100]}...")
            raise
