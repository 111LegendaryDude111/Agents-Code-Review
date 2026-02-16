import os

from ..domain import Issue, Severity


class PolicyManager:
    def __init__(
        self,
        max_comments: int = 15,
        max_inline: int = 8,
        max_per_file: int = 2,
    ):
        self.max_comments = max_comments
        self.max_inline = max_inline
        self.max_per_file = max_per_file

        self.min_confidence = {
            Severity.BLOCKER: float(
                os.getenv("AI_REVIEW_MIN_CONFIDENCE_BLOCKER", "0.9")
            ),
            Severity.IMPORTANT: float(
                os.getenv("AI_REVIEW_MIN_CONFIDENCE_IMPORTANT", "0.85")
            ),
            Severity.QUESTION: float(
                os.getenv("AI_REVIEW_MIN_CONFIDENCE_QUESTION", "0.7")
            ),
            Severity.NIT: float(os.getenv("AI_REVIEW_MIN_CONFIDENCE_NIT", "0.75")),
        }

    def apply_policy(self, issues: list[Issue]) -> list[Issue]:
        """
        Filter and prioritize issues based on policy.
        """
        filtered_issues = []
        for issue in issues:
            threshold = self.min_confidence.get(issue.severity, 0.75)
            if issue.confidence < threshold:
                continue

            # Strict Evidence Check
            if not issue.evidence or not issue.evidence.excerpt:
                continue

            if not issue.title.strip() or not issue.message.strip():
                continue

            # High-severity findings must include a concrete fix.
            if issue.severity in {Severity.BLOCKER, Severity.IMPORTANT}:
                suggestion = (issue.suggestion or "").strip()
                if len(suggestion) < 8:
                    continue

            # Helper: Generate fingerprint if missing
            if not issue.fingerprint:
                issue.fingerprint = (
                    f"{issue.path}:{issue.line_start}:{issue.line_end}:{issue.title}"
                )

            filtered_issues.append(issue)

        # 1. Deduplication (stable semantic key)
        seen = set()
        unique_issues = []
        for issue in filtered_issues:
            semantic_key = (
                issue.path,
                issue.line_start,
                issue.line_end,
                issue.severity.value,
                issue.title.strip().lower(),
            )
            if semantic_key not in seen:
                seen.add(semantic_key)
                unique_issues.append(issue)

        # 2. Sort by severity, then confidence (descending)
        severity_order = {
            Severity.BLOCKER: 0,
            Severity.IMPORTANT: 1,
            Severity.QUESTION: 2,
            Severity.NIT: 3,
        }
        unique_issues.sort(
            key=lambda x: (severity_order.get(x.severity, 4), -float(x.confidence))
        )

        # 3. Limit issue burst per file.
        limited_issues: list[Issue] = []
        file_counts: dict[str, int] = {}
        for issue in unique_issues:
            current = file_counts.get(issue.path, 0)
            if current >= self.max_per_file:
                continue
            file_counts[issue.path] = current + 1
            limited_issues.append(issue)

        # Provider handles the final inline slicing via max_inline.
        return limited_issues[: self.max_comments]
