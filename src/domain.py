from enum import Enum
from typing import List, Optional, Literal, Dict, Any
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
    commit_id: Optional[str] = None # The commit where the line exists

class Issue(BaseModel):
    id: str
    rule_id: Optional[str] = None # e.g. "security/sql-injection"
    fingerprint: Optional[str] = None # unique hash for deduplication
    severity: Severity
    category: Category
    title: str
    message: str
    path: str
    line_start: int
    line_end: int
    position: Optional[CommentPosition] = None
    evidence: Optional[Evidence] = None
    suggestion: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)

class DiffHunk(BaseModel):
    header: str
    lines: List[str]  # Raw lines including +/-
    old_start: int
    new_start: int
    old_lines: int
    new_lines: int

class ChangedFile(BaseModel):
    path: str
    original_path: Optional[str] = None  # For renames
    status: Literal["added", "modified", "deleted", "renamed"]
    language: Optional[str] = None
    hunks: List[DiffHunk] = []
    additions: int = 0
    deletions: int = 0
    is_generated: bool = False
    is_vendor: bool = False

class ReviewResult(BaseModel):
    summary: str
    issues: List[Issue] = []
    stats: Dict[str, Any] = {}
    decision: Literal["PASS", "WARN", "FAIL"]
