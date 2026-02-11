from ..domain import Issue, Severity


class PolicyManager:
    def __init__(self, max_comments: int = 15, max_inline: int = 8):
        self.max_comments = max_comments
        self.max_inline = max_inline

    def apply_policy(self, issues: list[Issue]) -> list[Issue]:
        """
        Filter and prioritize issues based on policy.
        """
        filtered_issues = []
        for issue in issues:
            # Gating: Confidence Threshold (0.8 for BLOCKER, 0.7 for IMPORTANT)
            threshold = 0.6
            if issue.severity == Severity.BLOCKER:
                threshold = 0.8
            elif issue.severity == Severity.IMPORTANT:
                threshold = 0.7

            if issue.confidence < threshold:
                continue

            # Strict Evidence Check
            if not issue.evidence or not issue.evidence.excerpt:
                continue

            # Helper: Generate fingerprint if missing
            if not issue.fingerprint:
                issue.fingerprint = f"{issue.path}:{issue.line_end}:{issue.title}"

            filtered_issues.append(issue)

        # 1. Deduplication (naive: by fingerprint)
        seen = set()
        unique_issues = []
        for issue in filtered_issues:
            if issue.fingerprint not in seen:
                seen.add(issue.fingerprint)
                unique_issues.append(issue)

        # 2. Sort by severity
        severity_order = {
            Severity.BLOCKER: 0,
            Severity.IMPORTANT: 1,
            Severity.QUESTION: 2,
            Severity.NIT: 3,
        }
        unique_issues.sort(key=lambda x: severity_order.get(x.severity, 4))

        # Provider handles the final inline slicing via max_inline.
        return unique_issues[: self.max_comments]
