import fnmatch
from dataclasses import dataclass

from ..domain import ChangedFile

DEFAULT_IGNORE_PATTERNS = [
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "go.sum",
    "*.min.js",
    "*.min.css",
    "dist/**",
    "build/**",
    "node_modules/**",
    "vendor/**",
    "__pycache__/**",
    "*.pyc",
]

RISK_PATTERNS = {
    "auth": ["**/auth/**", "**/login/**", "**/security/**", "**/permission/**"],
    "payment": ["**/payment/**", "**/billing/**", "**/stripe/**"],
    "core": ["**/core/**", "**/kernel/**", "**/infra/**"],
    "api": ["**/api/**", "**/routes/**", "**/controllers/**"],
    "deps": ["package.json", "pyproject.toml", "go.mod", "requirements.txt"],
}


@dataclass
class FilterResult:
    files_to_review: list[ChangedFile]
    excluded_files: list[ChangedFile]
    risk_score: int
    risk_factors: list[str]


class FileFilter:
    def __init__(self, ignore_patterns: list[str] | None = None):
        self.ignore_patterns = ignore_patterns or DEFAULT_IGNORE_PATTERNS

    def filter_files(self, files: list[ChangedFile]) -> FilterResult:
        to_review: list[ChangedFile] = []
        excluded: list[ChangedFile] = []
        risk_factors: set[str] = set()

        for file in files:
            if self._should_ignore(file.path):
                file.is_generated = True
                excluded.append(file)
                continue

            self._analyze_risk(file, risk_factors)
            to_review.append(file)

        risk_score = len(risk_factors) * 10
        return FilterResult(
            files_to_review=to_review,
            excluded_files=excluded,
            risk_score=risk_score,
            risk_factors=sorted(risk_factors),
        )

    def _should_ignore(self, path: str) -> bool:
        return any(fnmatch.fnmatch(path, pattern) for pattern in self.ignore_patterns)

    def _analyze_risk(self, file: ChangedFile, factors: set[str]) -> None:
        for category, patterns in RISK_PATTERNS.items():
            for pattern in patterns:
                if fnmatch.fnmatch(file.path, pattern):
                    factors.add(category)
                    break
