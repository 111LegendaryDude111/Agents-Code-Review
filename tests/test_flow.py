import unittest
from unittest.mock import MagicMock, patch
import json
from src.domain import ChangedFile, DiffHunk, Issue
from src.filters.filter import FileFilter
from src.review.analyzer import ReviewAnalyzer
from src.policy.manager import PolicyManager

class TestReviewFlow(unittest.TestCase):
    def test_filter_logic(self):
        files = [
            ChangedFile(path="src/main.py", status="modified", additions=10, deletions=2),
            ChangedFile(path="package-lock.json", status="modified", additions=100, deletions=0),
            ChangedFile(path="src/auth/login.py", status="added", additions=50, deletions=0)
        ]
        
        filtr = FileFilter()
        result = filtr.filter_files(files)
        
        self.assertEqual(len(result.files_to_review), 2)
        self.assertEqual(len(result.excluded_files), 1) # package-lock.json
        self.assertIn("auth", result.risk_factors)
        self.assertGreater(result.risk_score, 0)

    @patch("src.review.llm.LLMClient")
    def test_analyzer_triage(self, MockLLM):
        llm = MockLLM.return_value
        llm.get_completion.return_value = json.dumps({
            "files_to_review": ["src/main.py"],
            "focus_areas": ["logic"],
            "budget": "normal"
        })
        
        analyzer = ReviewAnalyzer(llm)
        filter_result = MagicMock()
        filter_result.files_to_review = [ChangedFile(path="src/main.py", status="modified")]
        filter_result.risk_score = 10
        
        plan = analyzer.triage(filter_result, {"title": "Test PR"})
        
        self.assertEqual(plan["files_to_review"], ["src/main.py"])

    @patch("src.review.llm.LLMClient")
    def test_review_adds_diff_evidence_and_passes_policy(self, MockLLM):
        llm = MockLLM.return_value
        llm.get_completion.return_value = json.dumps({
            "issues": [
                {
                    "id": "issue-1",
                    "severity": "IMPORTANT",
                    "category": "BUG",
                    "title": "Potential bug",
                    "message": "Check null handling.",
                    "line_start": 3,
                    "line_end": 3,
                    "confidence": 0.9
                }
            ]
        })

        analyzer = ReviewAnalyzer(llm)
        file = ChangedFile(
            path="src/main.py",
            status="modified",
            additions=2,
            deletions=1,
            hunks=[
                DiffHunk(
                    header="@@ -1,3 +1,4 @@",
                    lines=[" line1", "-line2", "+line2_new", "+line3_new"],
                    old_start=1,
                    new_start=1,
                    old_lines=3,
                    new_lines=4
                )
            ]
        )

        issues = analyzer.review_file(file, docs_evidence=[])
        self.assertEqual(len(issues), 1)
        self.assertIsNotNone(issues[0].evidence)
        self.assertEqual(issues[0].evidence.type.value, "DIFF")

        final = PolicyManager().apply_policy(issues)
        self.assertEqual(len(final), 1)

if __name__ == '__main__':
    unittest.main()
