import fnmatch
from typing import List, Dict
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
    "*.pyc"
]

RISK_PATTERNS = {
    "auth": ["**/auth/**", "**/login/**", "**/security/**", "**/permission/**"],
    "payment": ["**/payment/**", "**/billing/**", "**/stripe/**"],
    "core": ["**/core/**", "**/kernel/**", "**/infra/**"],
    "api": ["**/api/**", "**/routes/**", "**/controllers/**"],
    "deps": ["package.json", "pyproject.toml", "go.mod", "requirements.txt"]
}

class FilterResult:
    def __init__(self, files_to_review: List[ChangedFile], excluded_files: List[ChangedFile], risk_score: int, risk_factors: List[str]):
        self.files_to_review = files_to_review
        self.excluded_files = excluded_files
        self.risk_score = risk_score
        self.risk_factors = risk_factors

class FileFilter:
    def __init__(self, ignore_patterns: List[str] = None):
        self.ignore_patterns = ignore_patterns or DEFAULT_IGNORE_PATTERNS

    def filter_files(self, files: List[ChangedFile]) -> FilterResult:
        to_review = []
        excluded = []
        risk_score = 0
        risk_factors = set()

        for file in files:
            if self._should_ignore(file.path):
                file.is_generated = True # marking as generated/ignored
                excluded.append(file)
                continue
            
            # Check for risk factors
            self._analyze_risk(file, risk_factors)
            to_review.append(file)

        # Calculate final score based on factors
        risk_score = len(risk_factors) * 10 # arbitrary weight
        
        return FilterResult(to_review, excluded, risk_score, list(risk_factors))

    def _should_ignore(self, path: str) -> bool:
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False

    def _analyze_risk(self, file: ChangedFile, factors: set):
        for category, patterns in RISK_PATTERNS.items():
            for pattern in patterns:
                if fnmatch.fnmatch(file.path, pattern):
                    factors.add(category)
                    break
