from typing import Any

from ..domain import Category, ChangedFile, Evidence, EvidenceType, Issue, Severity
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
                    # Deletions are not present in the new-file line space.
                    continue

        if matched_lines:
            return "\n".join(matched_lines)[:500]

        # Fallback: take the first few lines from the first available hunk.
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
            return SafeJSONParser.parse(response)
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

            # Safe parsing with repair attempt
            try:
                data = SafeJSONParser.parse(response)
            except Exception:
                print(f"JSON Parse failed for {file.path}. Content: {response[:50]}...")
                return []

            issues: list[Issue] = []
            for item in data.get("issues", []):
                if not isinstance(item, dict):
                    continue

                raw_line_start = item.get("line_start", 1)
                raw_line_end = item.get("line_end", raw_line_start)
                line_start = max(1, int(raw_line_start))
                line_end = max(line_start, int(raw_line_end))
                evidence = self._build_issue_evidence(
                    file, docs_evidence, line_start, line_end
                )
                severity = self._parse_severity(item.get("severity"))
                category = self._parse_category(item.get("category"))
                raw_suggestion = item.get("suggestion")
                suggestion = str(raw_suggestion) if raw_suggestion is not None else None

                issues.append(
                    Issue(
                        id=str(item.get("id", "unknown")),
                        severity=severity,
                        category=category,
                        title=str(item.get("title", "Issue")),
                        message=str(item.get("message", "")),
                        path=file.path,
                        line_start=line_start,
                        line_end=line_end,
                        suggestion=suggestion,
                        confidence=float(item.get("confidence", 0.5)),
                        evidence=evidence,
                    )
                )
            return issues
        except Exception as e:
            print(f"Review failed for {file.path}: {e}")
            return []
