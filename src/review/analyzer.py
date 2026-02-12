from typing import Any

from pydantic import ValidationError

from ..domain import (
    Category,
    ChangedFile,
    Evidence,
    EvidenceType,
    FocusedReviewResponse,
    Issue,
    LLMIssueCandidate,
    Severity,
    TriagePlan,
)
from ..filters.filter import FilterResult
from .llm import LLMClient


class ReviewAnalyzer:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def _extract_diff_excerpt(
        self, file: ChangedFile, line_start: int, line_end: int
    ) -> str:
        """
        Extract a short diff excerpt around the target new-file line range.
        Falls back to the beginning of the first hunk when exact mapping is unavailable.
        """
        target_start = max(1, line_start)
        target_end = max(target_start, line_end)
        matched_lines: list[str] = []

        for hunk in file.hunks:
            new_line = hunk.new_start
            for raw_line in hunk.lines:
                prefix = raw_line[:1] if raw_line else ""
                if prefix in {"+", " "}:
                    if target_start <= new_line <= target_end:
                        matched_lines.append(raw_line[:200])
                    new_line += 1
                elif prefix == "-":
                    continue

        if matched_lines:
            return "\n".join(matched_lines)[:500]

        if file.hunks:
            fallback = "\n".join(file.hunks[0].lines[:5]).strip()
            if fallback:
                return fallback[:500]

        return "See changed diff context."

    def _build_issue_evidence(
        self,
        file: ChangedFile,
        docs_evidence: list[Evidence],
        line_start: int,
        line_end: int,
    ) -> Evidence:
        """
        Build evidence for each issue. Prefer project docs evidence; otherwise use DIFF evidence.
        """
        if docs_evidence:
            primary = docs_evidence[0]
            return Evidence(
                type=primary.type,
                source=primary.source,
                excerpt=(primary.excerpt or "See project documentation.")[:500],
            )

        return Evidence(
            type=EvidenceType.DIFF,
            source=f"{file.path}:{max(1, line_start)}",
            excerpt=self._extract_diff_excerpt(file, line_start, line_end),
        )

    def _parse_severity(self, value: Any) -> Severity:
        if isinstance(value, Severity):
            return value
        if isinstance(value, str):
            try:
                return Severity(value.upper())
            except ValueError:
                return Severity.NIT
        return Severity.NIT

    def _parse_category(self, value: Any) -> Category:
        if isinstance(value, Category):
            return value
        if isinstance(value, str):
            try:
                return Category(value.upper())
            except ValueError:
                return Category.STYLE
        return Category.STYLE

    def triage(
        self, filter_result: FilterResult, pr_meta: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Determine which files to review and set budget.
        """
        system_prompt = """You are a Code Review Triage agent.
Analyze the PR metadata and list of changed files.
Decide which files need a detailed review based on risk and complexity.
Output logic in JSON:
{
  "files_to_review": ["path/to/file1", "path/to/file2"],
  "focus_areas": ["security", "performance", "logic"],
  "budget": "high"
}
"""
        files_summary = "\n".join(
            f"{f.path} (+{f.additions}/-{f.deletions})"
            for f in filter_result.files_to_review
        )

        user_prompt = f"""
PR Title: {pr_meta.get('title')}
Description: {pr_meta.get('body')}
Risk Score: {filter_result.risk_score}
Risk Factors: {filter_result.risk_factors}

Changed Files:
{files_summary}
"""
        from ..safety.utils import SafeJSONParser

        try:
            response = self.llm.get_completion(
                system_prompt,
                user_prompt,
                response_format={"type": "json_object"},
            )
            cleaned = SafeJSONParser.clean_json_text(response)
            try:
                plan = TriagePlan.model_validate_json(cleaned)
                return plan.model_dump()
            except ValidationError as validation_error:
                print(f"Triage schema validation failed: {validation_error}")
                fallback_data = SafeJSONParser.parse(response)
                if isinstance(fallback_data, dict):
                    raw_files = fallback_data.get("files_to_review", [])
                    raw_focus = fallback_data.get("focus_areas", [])
                    raw_budget = fallback_data.get("budget", "normal")
                    raw_summary = fallback_data.get("summary")

                    plan = TriagePlan(
                        files_to_review=(
                            [str(item) for item in raw_files]
                            if isinstance(raw_files, list)
                            else []
                        ),
                        focus_areas=(
                            [str(item) for item in raw_focus]
                            if isinstance(raw_focus, list)
                            else []
                        ),
                        budget=str(raw_budget),
                        summary=str(raw_summary) if raw_summary is not None else None,
                    )
                    return plan.model_dump()
                raise
        except Exception as e:
            print(f"Triage failed (JSON error): {e}")
            # Fallback: review all filtered files
            return {"files_to_review": [f.path for f in filter_result.files_to_review]}

    def review_file(
        self, file: ChangedFile, docs_evidence: list[Evidence]
    ) -> list[Issue]:
        """
        Review a single file using LLM with safety and reliability.
        """
        system_prompt = """You are a Senior Code Reviewer.
Analyze the provided code diff and documentation evidence.
Identify list of issues.
Output strictly JSON:
{
  "issues": [
    {
      "id": "unique_id",
      "severity": "BLOCKER|IMPORTANT|NIT|QUESTION",
      "category": "BUG|SECURITY|STYLE",
      "title": "Short title",
      "message": "Detailed explanation",
      "line_start": 10,
      "line_end": 12,
      "suggestion": "replacement code if any",
      "confidence": 0.95
    }
  ]
}
"""
        diff_content = ""
        for hunk in file.hunks:
            diff_content += f"{hunk.header}\n"
            diff_content += "\n".join(hunk.lines) + "\n"

        evidence_text = "\n".join([f"[{e.source}]: {e.excerpt}" for e in docs_evidence])

        user_prompt = f"""
File: {file.path}
Additions: {file.additions}, Deletions: {file.deletions}

Relevant Generic Docs:
{evidence_text}

Diff:
{diff_content}
"""
        from ..safety.utils import SafeJSONParser, SecretRedactor

        redactor = SecretRedactor()

        # Redact secrets before sending to LLM
        safe_user_prompt = redactor.redact(user_prompt)

        try:
            response = self.llm.get_completion(
                system_prompt,
                safe_user_prompt,
                response_format={"type": "json_object"},
            )

            try:
                cleaned = SafeJSONParser.clean_json_text(response)
                review_response = FocusedReviewResponse.model_validate_json(cleaned)
                issue_candidates = review_response.issues
            except ValidationError as validation_error:
                print(
                    f"Focused schema validation failed for {file.path}: {validation_error}"
                )
                try:
                    data = SafeJSONParser.parse(response)
                except Exception:
                    print(
                        f"JSON Parse failed for {file.path}. Content: {response[:50]}..."
                    )
                    return []

                raw_issues = data.get("issues", []) if isinstance(data, dict) else []
                issue_candidates: list[LLMIssueCandidate] = []
                if isinstance(raw_issues, list):
                    for raw_issue in raw_issues:
                        if not isinstance(raw_issue, dict):
                            continue
                        try:
                            issue_candidates.append(
                                LLMIssueCandidate.model_validate(raw_issue)
                            )
                        except ValidationError:
                            continue

            issues: list[Issue] = []
            for candidate in issue_candidates:
                line_start = max(1, int(candidate.line_start))
                line_end = max(line_start, int(candidate.line_end))
                evidence = self._build_issue_evidence(
                    file, docs_evidence, line_start, line_end
                )
                severity = self._parse_severity(candidate.severity)
                category = self._parse_category(candidate.category)

                issues.append(
                    Issue(
                        id=candidate.id,
                        severity=severity,
                        category=category,
                        title=candidate.title,
                        message=candidate.message,
                        path=file.path,
                        line_start=line_start,
                        line_end=line_end,
                        suggestion=candidate.suggestion,
                        confidence=float(candidate.confidence),
                        evidence=evidence,
                    )
                )
            return issues
        except Exception as e:
            print(f"Review failed for {file.path}: {e}")
            return []
