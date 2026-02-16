import json
import unittest
from unittest.mock import MagicMock

from src.domain import ChangedFile
from src.filters.filter import FilterResult
from src.review.analyzer import ReviewAnalyzer


class TestAnalyzerContext(unittest.TestCase):
    def test_project_context_is_injected_into_prompts(self):
        llm = MagicMock()
        llm.get_completion.return_value = json.dumps(
            {
                "files_to_review": ["src/main.py"],
                "focus_areas": ["logic"],
                "budget": "normal",
                "summary": "ok",
            }
        )

        analyzer = ReviewAnalyzer(llm)
        changed_file = ChangedFile(
            path="src/main.py",
            status="modified",
            additions=2,
            deletions=1,
        )
        filter_result = FilterResult(
            files_to_review=[changed_file],
            excluded_files=[],
            risk_score=10,
            risk_factors=["core"],
        )

        analyzer.triage(
            filter_result,
            {"title": "Test PR", "body": "Context prompt test"},
            project_context="Project policies and architecture",
        )
        triage_user_prompt = llm.get_completion.call_args[0][1]
        self.assertIn("Project Context:", triage_user_prompt)

        llm.get_completion.reset_mock()
        llm.get_completion.return_value = json.dumps({"issues": []})
        analyzer.review_file(
            changed_file,
            docs_evidence=[],
            project_context="Project policies and architecture",
        )
        review_user_prompt = llm.get_completion.call_args[0][1]
        self.assertIn("Project Context:", review_user_prompt)


if __name__ == "__main__":
    unittest.main()
