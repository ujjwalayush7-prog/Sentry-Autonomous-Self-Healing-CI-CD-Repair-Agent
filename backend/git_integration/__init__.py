"""
Git Integration Package
Provides GitHub REST API PR creation and Git repository hook automation.
"""

from .models import PRCreationRequest, PRCreationResult
from .github_client import (
    GitHubPRClient,
    parse_github_repo,
    build_pr_title,
    build_pr_body,
)
from .repo_hook import execute_pr_hook

__all__ = [
    "PRCreationRequest",
    "PRCreationResult",
    "GitHubPRClient",
    "parse_github_repo",
    "build_pr_title",
    "build_pr_body",
    "execute_pr_hook",
]
