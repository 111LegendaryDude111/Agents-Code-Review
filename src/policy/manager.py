from typing import List
from ..domain import Issue, Severity

class PolicyManager:
    def __init__(self, max_comments: int = 15, max_inline: int = 8):
        self.max_comments = max_comments
        self.max_inline = max_inline

    def apply_policy(self, issues: List[Issue]) -> List[Issue]:
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
                # Downgrade or Drop? For now, we drop low confidence noise.
                continue

            # Strict Evidence Check
            if not issue.evidence or not issue.evidence.excerpt:
                # Issue has no evidence. Drop or convert to Question?
                # Per critical requirements, we drop issues without evidence to reduce hallucination.
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
            Severity.NIT: 3
        }
        unique_issues.sort(key=lambda x: severity_order.get(x.severity, 4))

        # 3. Limit total issues and inline issues (implicit contract: return all authorized issues)
        # We need to respect max_comments total.
        final_list = unique_issues[:self.max_comments]
        
        # We assume the provider will handle the max_inline slicing, OR we can mark them?
        # Actually, let's just return the top N.
        # But wait, max_inline is different from max_total?
        # Typically: show top N total, and of those, post top M as inline.
        # Here we just return the list allowed for publication.
        return final_list
