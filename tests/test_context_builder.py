import os
import tempfile
import unittest

from src.context_builder.builder import ContextBuilder


class TestContextBuilder(unittest.TestCase):
    def test_build_save_load_and_format_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = os.path.join(tmp, "src")
            os.makedirs(src_dir, exist_ok=True)

            with open(os.path.join(tmp, "README.md"), "w", encoding="utf-8") as f:
                f.write(
                    "# Demo Project\n\nThis project validates API payloads and business rules."
                )

            with open(os.path.join(src_dir, "main.py"), "w", encoding="utf-8") as f:
                f.write("def main():\n    return 42\n")

            builder = ContextBuilder(workspace_root=tmp)
            docs = builder.load_project_docs()
            self.assertEqual(len(docs), 1)

            context = builder.build_project_context(docs_paths=docs)
            self.assertIn("project_summary", context)
            self.assertIn("docs", context)

            context_path = os.path.join(tmp, "project-context.json")
            builder.save_project_context(context_path, context)
            loaded = builder.load_project_context(context_path)

            if loaded is None:
                self.fail("Expected context to be loaded from saved file")

            rendered = builder.format_project_context(
                loaded, file_path="src/main.py", max_chars=800
            )
            self.assertIn("Project Summary:", rendered)
            self.assertIn("Current File: src/main.py", rendered)


if __name__ == "__main__":
    unittest.main()
