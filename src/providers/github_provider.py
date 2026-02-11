import re
from typing import Literal

from github import Auth, Github
from github.IssueComment import IssueComment
from github.PullRequest import PullRequest
from github.Repository import Repository

from ..domain import ChangedFile, DiffHunk, Issue
from .base import BaseProvider


class GitHubProvider(BaseProvider):
    def __init__(self, token: str, repo_slug: str, pr_number: int):
        self.github = Github(auth=Auth.Token(token))
        self.repo: Repository = self.github.get_repo(repo_slug)
        self.pr: PullRequest = self.repo.get_pull(pr_number)
        self.user = self.github.get_user()

    def fetch_pr_metadata(self) -> dict:
        return {
            "number": self.pr.number,
            "title": self.pr.title,
            "body": self.pr.body,
            "author": self.pr.user.login,
            "base_sha": self.pr.base.sha,
            "head_sha": self.pr.head.sha,
            "state": self.pr.state,
        }

    def get_changed_files(self) -> list[ChangedFile]:
        files: list[ChangedFile] = []
        gh_files = self.pr.get_files()
        status_map: dict[str, Literal["added", "modified", "renamed", "deleted"]] = {
            "added": "added",
            "modified": "modified",
            "renamed": "renamed",
            "removed": "deleted",
        }

        for file in gh_files:
            if file.status == "removed":
                files.append(
                    ChangedFile(
                        path=file.filename,
                        status="deleted",
                        deletions=file.deletions,
                        additions=file.additions,
                    )
                )
                continue

            patch = file.patch or ""
            hunks = self._parse_patch(patch)
            mapped_status = status_map.get(file.status, "modified")

            files.append(
                ChangedFile(
                    path=file.filename,
                    original_path=file.previous_filename,
                    status=mapped_status,
                    additions=file.additions,
                    deletions=file.deletions,
                    hunks=hunks,
                )
            )

        return files

    def _parse_patch(self, patch: str) -> list[DiffHunk]:
        """
        Parses a unified diff patch string into DiffHunk objects.
        """
        if not patch:
            return []

        hunks: list[DiffHunk] = []
        lines = patch.split("\n")
        current_hunk: DiffHunk | None = None
        current_lines: list[str] = []

        hunk_header_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

        for line in lines:
            match = hunk_header_re.match(line)
            if match:
                if current_hunk:
                    current_hunk.lines = current_lines
                    hunks.append(current_hunk)

                old_start = int(match.group(1))
                old_len = int(match.group(2)) if match.group(2) else 1
                new_start = int(match.group(3))
                new_len = int(match.group(4)) if match.group(4) else 1

                current_hunk = DiffHunk(
                    header=line,
                    lines=[],
                    old_start=old_start,
                    new_start=new_start,
                    old_lines=old_len,
                    new_lines=new_len,
                )
                current_lines = []
            elif current_hunk:
                current_lines.append(line)

        if current_hunk:
            current_hunk.lines = current_lines
            hunks.append(current_hunk)

        return hunks

    def post_summary_comment(self, body: str) -> None:
        """
        Post or update the main review summary.
        Uses a hidden marker to identify the bot's comment.
        """
        marker = "<!-- ai-review:summary -->"
        final_body = f"{marker}\n{body}"
        existing_comment = self._find_summary_comment(marker)

        try:
            if existing_comment:
                existing_comment.edit(final_body)
            else:
                self.pr.create_issue_comment(final_body)
        except Exception as e:
            print(f"Warning: Failed to post summary comment: {e}")

    def _find_summary_comment(self, marker: str) -> IssueComment | None:
        for comment in self.pr.get_issue_comments():
            body = comment.body or ""
            if marker in body:
                return comment
        return None

    def _append_summary_notice(self, notice: str) -> None:
        """
        Append a publication warning to existing summary instead of overwriting it.
        """
        marker = "<!-- ai-review:summary -->"
        formatted_notice = f"**Publication warning**: {notice}"
        existing_comment = self._find_summary_comment(marker)

        try:
            if existing_comment:
                body = existing_comment.body or ""
                if formatted_notice in body:
                    return
                existing_comment.edit(f"{body}\n\n---\n{formatted_notice}")
            else:
                # If summary does not exist, create one with marker and warning.
                self.post_summary_comment(formatted_notice)
        except Exception as e:
            print(f"Warning: Failed to append summary notice: {e}")

    def post_inline_comments(self, issues: list[Issue]) -> None:
        """
        Post review comments on the PR.
        Consolidates comments into a Review.
        """
        comments = []
        for issue in issues:
            path = issue.position.file_path if issue.position else issue.path
            line = issue.position.line_number if issue.position else issue.line_end
            side = issue.position.side if issue.position else "RIGHT"

            if not path or line <= 0:
                print(f"Skipping inline comment with invalid position: {issue.id}")
                continue

            comments.append(
                {
                    "path": path,
                    "body": (
                        f"**[{issue.severity.value}]** {issue.title}\n\n"
                        f"{issue.message}\n\nconfidence: {issue.confidence:.2f}"
                    ),
                    "line": line,
                    "side": side,
                }
            )

        if comments:
            try:
                self.pr.create_review(
                    body="AI Code Review Results (Inline)",
                    comments=comments,
                    event="COMMENT",
                )
            except Exception as e:
                print(f"Batch inline publish failed: {e}. Retrying per comment.")
                posted = 0
                failed = 0

                for comment in comments:
                    try:
                        self.pr.create_review(
                            body="AI Code Review Results (Inline)",
                            comments=[comment],
                            event="COMMENT",
                        )
                        posted += 1
                    except Exception as item_error:
                        failed += 1
                        print(
                            f"Failed inline comment for {comment['path']}:{comment['line']}: {item_error}"
                        )

                if failed > 0:
                    self._append_summary_notice(
                        f"Inline comments posted partially. Posted: {posted}, failed: {failed}."
                    )
