import os
import re
from typing import List, Dict, Any, Optional
from github import Github, Auth
from github.PullRequest import PullRequest
from github.Repository import Repository

from .base import BaseProvider
from ..domain import ChangedFile, Issue, DiffHunk

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

    def get_changed_files(self) -> List[ChangedFile]:
        files = []
        # Get files from the PR. note: this is paginated, need to iterate
        gh_files = self.pr.get_files()
        
        for file in gh_files:
            if file.status == "removed":
                # We generally don't review deleted files' content, but maybe we want to know
                # For now, let's include them but marked as deletions
                files.append(ChangedFile(
                    path=file.filename,
                    status="deleted",
                    deletions=file.deletions,
                    additions=file.additions
                ))
                continue
                
            patch = file.patch or ""
            hunks = self._parse_patch(patch)
            
            files.append(ChangedFile(
                path=file.filename,
                original_path=file.previous_filename,
                status=file.status,  # added, modified, renamed
                additions=file.additions,
                deletions=file.deletions,
                hunks=hunks
            ))
            
        return files

    def _parse_patch(self, patch: str) -> List[DiffHunk]:
        """
        Parses a unified diff patch string into DiffHunk objects.
        """
        if not patch:
            return []
            
        hunks = []
        lines = patch.split('\n')
        
        current_hunk = None
        current_lines = []
        
        # Regex to parse the hunk header: @@ -old_start,old_lines +new_start,new_lines @@
        hunk_header_re = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
        
        for line in lines:
            match = hunk_header_re.match(line)
            if match:
                # Save previous hunk if exists
                if current_hunk:
                    current_hunk.lines = current_lines
                    hunks.append(current_hunk)
                
                # Start new hunk
                old_start = int(match.group(1))
                old_len = int(match.group(2)) if match.group(2) else 1
                new_start = int(match.group(3))
                new_len = int(match.group(4)) if match.group(4) else 1
                
                # Create the hunk object (lines will be filled)
                current_hunk = DiffHunk(
                    header=line,
                    lines=[],
                    old_start=old_start,
                    new_start=new_start,
                    old_lines=old_len,
                    new_lines=new_len
                )
                current_lines = []
            else:
                if current_hunk:
                    current_lines.append(line)
        
        # Append the last hunk
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

    def _find_summary_comment(self, marker: str):
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

    def post_inline_comments(self, issues: List[Issue]) -> None:
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

            comments.append({
                "path": path,
                "body": f"**[{issue.severity}]** {issue.title}\n\n{issue.message}\n\nconfidence: {issue.confidence:.2f}",
                "line": line,
                "side": side
            })
        
        if comments:
            try:
                self.pr.create_review(body="AI Code Review Results (Inline)", comments=comments, event="COMMENT")
            except Exception as e:
                print(f"Batch inline publish failed: {e}. Retrying per comment.")
                posted = 0
                failed = 0

                for comment in comments:
                    try:
                        self.pr.create_review(
                            body="AI Code Review Results (Inline)",
                            comments=[comment],
                            event="COMMENT"
                        )
                        posted += 1
                    except Exception as item_error:
                        failed += 1
                        print(f"Failed inline comment for {comment['path']}:{comment['line']}: {item_error}")

                if failed > 0:
                    self._append_summary_notice(
                        f"Inline comments posted partially. Posted: {posted}, failed: {failed}."
                    )
