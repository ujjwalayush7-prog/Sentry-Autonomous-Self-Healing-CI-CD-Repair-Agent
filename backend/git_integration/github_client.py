"""
GitHub REST API Client (PAT-based authentication)
Handles repository metadata lookup, PR title/body generation, and Pull Request creation.
Reads token exclusively from environment variable GITHUB_PAT (or GITHUB_TOKEN fallback).
"""

import os
import re
import logging
from typing import Any, Dict, Optional, Tuple
import requests

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


def parse_github_repo(repo_url: str) -> Tuple[str, str]:
    """
    Extracts (owner, repo) from a GitHub URL.
    Supports:
      - https://github.com/owner/repo
      - https://github.com/owner/repo.git
      - git@github.com:owner/repo.git
    """
    cleaned = repo_url.strip().rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]

    https_match = re.search(r"github\.com[:/]([^/]+)/([^/]+)$", cleaned)
    if not https_match:
        raise ValueError(f"Could not parse GitHub owner/repo from URL: {repo_url}")

    return https_match.group(1), https_match.group(2)


def build_pr_title(target_file: str, explanation: str) -> str:
    """
    Derives a clean, one-line root cause PR title from the target file and explanation.
    """
    basename = os.path.basename(target_file.replace("\\", "/")) or target_file
    # Take the first sentence of the explanation
    first_sentence = explanation.strip().split(".")[0].strip()
    if not first_sentence:
        first_sentence = f"Resolve test failure in {basename}"

    # Keep title under ~90 chars for clean GitHub display
    prefix = f"fix({basename}): "
    max_summary_len = 100 - len(prefix)
    if len(first_sentence) > max_summary_len:
        first_sentence = first_sentence[:max_summary_len - 3].rstrip() + "..."

    return f"{prefix}{first_sentence}"


def build_pr_body(
    target_file: str,
    explanation: str,
    root_cause_hypothesis: str,
    before_counts: Dict[str, int],
    after_counts: Dict[str, int],
    unified_diff: str,
    model_id: str = "ibm/granite-3-8b-instruct",
    attempts_used: int = 1,
) -> str:
    """
    Builds the structured Markdown PR body containing:
    1. Root cause explanation & fix summary
    2. Before/after test suite counts
    3. The validated unified diff
    """
    b_pass = before_counts.get("tests_passed", 0)
    b_fail = before_counts.get("tests_failed", 0)
    b_tot = before_counts.get("tests_total", 0)

    a_pass = after_counts.get("tests_passed", 0)
    a_fail = after_counts.get("tests_failed", 0)
    a_tot = after_counts.get("tests_total", 0)

    return f"""## Sentry Self-Healing CI/CD — Automated Root-Cause Fix

### 1. Root Cause & Fix Summary
**Target File:** `{target_file}`

{explanation}

#### Diagnostic Hypothesis
> {root_cause_hypothesis}

---

### 2. Test Suite Validation (Before vs. After)

| Metric | Before Patch (Red) | After Patch (Green) |
| :--- | :---: | :---: |
| **Total Tests** | {b_tot} | {a_tot} |
| **Passed** | {b_pass} | **{a_pass}** |
| **Failed** | {b_fail} | **{a_fail}** |
| **Suite Status** | `FAILED` | `PASSED` |

---

### 3. Validated Minimal Patch
```diff
{unified_diff.strip()}
```

---
*Generated autonomously by **Sentry** (Reasoning Backbone: `{model_id}` | Validated in {attempts_used} attempt(s)).*
"""


class GitHubPRClient:
    """Thin REST wrapper around GitHub API v3 using Personal Access Token (PAT)."""

    def __init__(self, pat: Optional[str] = None):
        self.pat = pat or os.environ.get("GITHUB_PAT") or os.environ.get("GITHUB_TOKEN")
        if not self.pat:
            raise ValueError(
                "GitHub Personal Access Token not found. "
                "Set the GITHUB_PAT environment variable."
            )
        self.headers = {
            "Authorization": f"Bearer {self.pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def get_default_branch(self, owner: str, repo: str) -> str:
        """Returns the repository's default branch (e.g. 'main' or 'master')."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
        resp = requests.get(url, headers=self.headers, timeout=20)
        resp.raise_for_status()
        return resp.json().get("default_branch", "main")

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
    ) -> Dict[str, Any]:
        """Opens a Pull Request via POST /repos/{owner}/{repo}/pulls."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
        }
        resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"GitHub PR creation failed ({resp.status_code}): {resp.text}"
            )
        return resp.json()
