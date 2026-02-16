import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..domain import ChangedFile

DOC_FILENAMES = {
    "README.MD",
    "CONTRIBUTING.MD",
    "STYLE_GUIDE.MD",
    "ARCHITECTURE.MD",
}
IGNORED_DIRS = {
    ".git",
    ".venv",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "vendor",
    "dist",
    "build",
}
DEFAULT_CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".java",
    ".kt",
    ".rb",
    ".rs",
    ".php",
    ".swift",
    ".scala",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".sh",
    ".bash",
    ".zsh",
    ".ps1",
    ".sql",
}
DEFAULT_CONTEXT_MAX_CHARS = 2400
DEFAULT_DOC_EXCERPT_CHARS = 700


class ContextBuilder:
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = workspace_root
        self.docs_cache: dict[str, str] = {}

    def _iter_project_files(self):
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [
                d
                for d in dirs
                if d not in IGNORED_DIRS and not d.startswith(".pytest_cache")
            ]
            for filename in files:
                yield os.path.join(root, filename)

    def _read_text_file(self, path: str) -> str:
        normalized_path = os.path.abspath(path)
        if normalized_path in self.docs_cache:
            return self.docs_cache[normalized_path]
        try:
            with open(normalized_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            content = ""
        self.docs_cache[normalized_path] = content
        return content

    def _to_excerpt(self, text: str, max_chars: int = DEFAULT_DOC_EXCERPT_CHARS) -> str:
        compact = " ".join(line.strip() for line in text.splitlines() if line.strip())
        if len(compact) <= max_chars:
            return compact
        return f"{compact[: max_chars - 3].rstrip()}..."

    def _collect_codebase_stats(self) -> dict[str, Any]:
        ext_counter: Counter[str] = Counter()
        top_dir_counter: Counter[str] = Counter()
        total_code_files = 0

        for abs_path in self._iter_project_files():
            relative_path = os.path.relpath(abs_path, self.workspace_root).replace(
                os.sep, "/"
            )
            suffix = Path(relative_path).suffix.lower()
            if suffix not in DEFAULT_CODE_EXTENSIONS:
                continue
            total_code_files += 1
            ext_counter[suffix] += 1
            top = relative_path.split("/")[0] if "/" in relative_path else "."
            top_dir_counter[top] += 1

        top_dirs = [
            {"path": path, "files": count}
            for path, count in top_dir_counter.most_common(8)
        ]
        top_exts = [
            {"ext": ext, "files": count} for ext, count in ext_counter.most_common(8)
        ]
        return {
            "total_code_files": total_code_files,
            "top_directories": top_dirs,
            "top_extensions": top_exts,
        }

    def load_project_docs(self) -> list[str]:
        docs: list[str] = []
        for file_path in self._iter_project_files():
            if os.path.basename(file_path).upper() in DOC_FILENAMES:
                docs.append(file_path)
        return sorted(docs)

    def build_project_context(
        self,
        docs_paths: list[str] | None = None,
        changed_files: list[ChangedFile] | None = None,
    ) -> dict[str, Any]:
        docs = docs_paths or self.load_project_docs()
        doc_entries: list[dict[str, str]] = []

        for path in docs[:6]:
            content = self._read_text_file(path)
            if not content.strip():
                continue
            rel_path = os.path.relpath(path, self.workspace_root).replace(os.sep, "/")
            doc_entries.append(
                {
                    "path": rel_path,
                    "excerpt": self._to_excerpt(content, DEFAULT_DOC_EXCERPT_CHARS),
                }
            )

        changed_paths: list[str] = []
        if changed_files:
            seen_paths: set[str] = set()
            for file in changed_files:
                if file.path in seen_paths:
                    continue
                seen_paths.add(file.path)
                changed_paths.append(file.path)
                if len(changed_paths) >= 20:
                    break

        codebase_stats = self._collect_codebase_stats()
        summary = (
            f"Code files: {codebase_stats['total_code_files']}. "
            f"Top directories: {', '.join(item['path'] for item in codebase_stats['top_directories'][:4]) or 'n/a'}."
        )

        return {
            "version": 1,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "workspace_root": os.path.abspath(self.workspace_root),
            "project_summary": summary,
            "review_guidelines": [
                "Focus on verifiable defects from diff.",
                "Prioritize correctness, security, and performance.",
                "Avoid style-only comments unless they cause real impact.",
            ],
            "changed_paths": changed_paths,
            "docs": doc_entries,
            "codebase": codebase_stats,
        }

    def save_project_context(self, path: str, context: dict[str, Any]) -> None:
        output_path = Path(path)
        if output_path.parent and str(output_path.parent) != ".":
            output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(context, f, ensure_ascii=False, indent=2)

    def load_project_context(self, path: str) -> dict[str, Any] | None:
        input_path = Path(path)
        if not input_path.exists():
            return None
        try:
            with input_path.open(encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return None
        if isinstance(data, dict):
            return data
        return None

    def format_project_context(
        self,
        context: dict[str, Any],
        file_path: str | None = None,
        max_chars: int = DEFAULT_CONTEXT_MAX_CHARS,
    ) -> str:
        summary = str(context.get("project_summary") or "").strip()
        guidelines = context.get("review_guidelines", [])
        codebase = context.get("codebase", {})
        docs = context.get("docs", [])
        changed_paths = context.get("changed_paths", [])

        lines: list[str] = []
        if summary:
            lines.append("Project Summary:")
            lines.append(summary)

        if file_path:
            lines.append("")
            lines.append(f"Current File: {file_path}")
            related = [
                path
                for path in changed_paths
                if path == file_path
                or path.startswith(file_path.rsplit("/", 1)[0] + "/")
                or file_path.startswith(path.rsplit("/", 1)[0] + "/")
            ][:5]
            if related:
                lines.append("Related Changed Paths:")
                for path in related:
                    lines.append(f"- {path}")

        top_dirs = (
            codebase.get("top_directories", []) if isinstance(codebase, dict) else []
        )
        if top_dirs:
            lines.append("")
            lines.append("Architecture Hints:")
            for item in top_dirs[:5]:
                if isinstance(item, dict):
                    lines.append(
                        f"- {item.get('path', 'unknown')}: {item.get('files', 0)} files"
                    )

        if isinstance(guidelines, list) and guidelines:
            lines.append("")
            lines.append("Review Guidelines:")
            for guideline in guidelines[:6]:
                lines.append(f"- {guideline}")

        if isinstance(docs, list) and docs:
            lines.append("")
            lines.append("Reference Docs:")
            for entry in docs[:3]:
                if not isinstance(entry, dict):
                    continue
                path = str(entry.get("path", "unknown"))
                excerpt = str(entry.get("excerpt", "")).strip()
                if excerpt:
                    lines.append(f"- {path}: {excerpt}")

        rendered = "\n".join(lines).strip()
        if len(rendered) <= max_chars:
            return rendered
        return f"{rendered[: max_chars - 3].rstrip()}..."

    def normalize_changes(self, files: list[ChangedFile]) -> list[ChangedFile]:
        return files
