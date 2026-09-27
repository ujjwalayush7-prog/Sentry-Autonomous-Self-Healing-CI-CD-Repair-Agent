"""
Git/Repo Integration Layer - Data Models
Structured inputs and outputs for automated branch, commit, push, and GitHub PR creation.
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class PRCreationRequest:
    """Input payload required to execute the Git/PR hook after validation succeeds."""
    repo_url: str
    target_file: str
    unified_diff: str
    explanation: str
    root_cause_hypothesis: str
    before_counts: Dict[str, int]
    after_counts: Dict[str, int]
    commit_sha: Optional[str] = None
    base_branch: Optional[str] = None
    model_id: str = "ibm/granite-3-8b-instruct"
    attempts_used: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PRCreationResult:
    """Result returned by the Git/PR hook."""
    success: bool
    pr_url: str
    pr_number: int
    title: str
    body: str
    branch_name: str
    base_branch: str
    commit_sha: str
    repo_full_name: str
    event: Dict[str, Any]
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
