import os
from typing import List, Optional
from ..domain import ChangedFile

class ContextBuilder:
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = workspace_root
        self.docs_cache = {}

    def load_project_docs(self) -> List[str]:
        """
        Load project documentation files (CONTRIBUTING, README, etc).
        For now, just return a list of paths or content.
        """
        docs = []
        # TODO: Implement doc discovery logic
        for root, dirs, files in os.walk(self.workspace_root):
            for file in files:
                if file.upper() in ["CONTRIBUTING.MD", "STYLE_GUIDE.MD", "README.MD"]:
                    docs.append(os.path.join(root, file))
        return docs

    def normalize_changes(self, files: List[ChangedFile]) -> List[ChangedFile]:
        """
        Normalize and enrich changed files.
        Count tokens, detect languages, etc.
        """
        # For now, just pass through
        return files
