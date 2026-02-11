from abc import ABC, abstractmethod
from typing import List, Optional
from ..domain import ChangedFile, Issue

class BaseProvider(ABC):
    @abstractmethod
    def fetch_pr_metadata(self) -> dict:
        """Fetch basic metadata about the PR (title, description, author, etc)."""
        pass

    @abstractmethod
    def get_changed_files(self) -> List[ChangedFile]:
        """Get list of changed files with diff hunks."""
        pass

    @abstractmethod
    def post_summary_comment(self, body: str) -> None:
        """Post the main review summary."""
        pass

    @abstractmethod
    def post_inline_comments(self, issues: List[Issue]) -> None:
        """Post inline comments on specific lines."""
        pass
