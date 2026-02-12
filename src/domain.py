from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class Severity(str, Enum):
    BLOCKER = "BLOCKER"
    IMPORTANT = "IMPORTANT"
    NIT = "NIT"
    QUESTION = "QUESTION"


class Category(str, Enum):
    STYLE = "STYLE"
    ARCH = "ARCH"
    BUG = "BUG"
    SECURITY = "SECURITY"
    PERF = "PERF"
    TESTING = "TESTING"
    DOCS = "DOCS"


class EvidenceType(str, Enum):
    DOC = "DOC"
    DIFF = "DIFF"


class TriageBudget(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class Evidence(BaseModel):
    type: EvidenceType
    source: str
    excerpt: str = Field(..., max_length=500)


class CommentPosition(BaseModel):
    """
    Unified position for inline comments.
    GitHub uses (commit_id, path, line, side).
    GitLab uses (base_sha, start_sha, head_sha, position_type, new_path, new_line).
    We store generic info here and adapters map it.
    """

    file_path: str
    line_number: int
    side: Literal["LEFT", "RIGHT"] = "RIGHT"
    commit_id: str | None = None  # The commit where the line exists


class Issue(BaseModel):
    id: str
    rule_id: str | None = None  # e.g. "security/sql-injection"
    fingerprint: str | None = None  # unique hash for deduplication
    severity: Severity
    category: Category
    title: str
    message: str
    path: str
    line_start: int
    line_end: int
    position: CommentPosition | None = None
    evidence: Evidence | None = None
    suggestion: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)


class DiffHunk(BaseModel):
    header: str
    lines: list[str]  # Raw lines including +/-
    old_start: int
    new_start: int
    old_lines: int
    new_lines: int


class ChangedFile(BaseModel):
    path: str
    original_path: str | None = None  # For renames
    status: Literal["added", "modified", "deleted", "renamed"]
    language: str | None = None
    hunks: list[DiffHunk] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    is_generated: bool = False
    is_vendor: bool = False


class TriagePlan(BaseModel):
    files_to_review: list[str] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    budget: TriageBudget = TriageBudget.NORMAL
    summary: str | None = None


class LLMIssueCandidate(BaseModel):
    id: str = Field(default_factory=lambda: f"llm-{uuid4().hex[:12]}")
    severity: Severity = Severity.NIT
    category: Category = Category.STYLE
    title: str = "Issue"
    message: str = ""
    line_start: int | None = None
    line_end: int | None = None
    suggestion: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class FocusedReviewResponse(BaseModel):
    issues: list[LLMIssueCandidate] = Field(default_factory=list)


class ReviewResult(BaseModel):
    summary: str
    issues: list[Issue] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)
    decision: Literal["PASS", "WARN", "FAIL"]
