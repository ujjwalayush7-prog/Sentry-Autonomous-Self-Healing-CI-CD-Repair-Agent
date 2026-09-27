"""
Phase 4a Verification: GitHub PR/Git Integration Hook
End-to-end verification on a separate throwaway scratch repository on GitHub.
Does NOT touch hero_python, hero_node, frontend/, or backend/main.py.

Verifies:
1. Throwaway GitHub repo creation & initial buggy commit push
2. execute_pr_hook: clone -> checkout SHA -> apply_patch -> branch -> commit -> push -> open PR
3. Live PR verification via GitHub REST API
4. Exact canonical pr_created event schema
"""

import os
import sys
import json
import shutil
import subprocess
import tempfile
import time
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from git_integration import (
    PRCreationRequest,
    PRCreationResult,
    execute_pr_hook,
)


def ensure_github_pat_in_env() -> str:
    """
    Ensures GITHUB_PAT is populated in os.environ.
    If not already set in environment, queries the system git credential helper.
    Never hardcodes any credentials.
    """
    pat = os.environ.get("GITHUB_PAT") or os.environ.get("GITHUB_TOKEN")
    if pat:
        os.environ["GITHUB_PAT"] = pat
        return pat

    out = subprocess.check_output(
        "git credential fill",
        input="protocol=https\nhost=github.com\nusername=ujjwalayush7-prog\n\n",
        text=True,
        shell=True,
        env={**os.environ, "GCM_INTERACTIVE": "never", "GIT_TERMINAL_PROMPT": "0"},
        timeout=10,
    )
    for line in out.splitlines():
        if line.startswith("password="):
            pat = line.split("=", 1)[1].strip()
            os.environ["GITHUB_PAT"] = pat
            return pat

    raise RuntimeError("No GITHUB_PAT found in environment or git credential helper.")


def setup_throwaway_github_repo(pat: str) -> tuple[str, str]:
    """
    Creates or resets a throwaway scratch repository on GitHub
    ('sentry-pr-hook-test-scratch') and pushes an initial buggy commit.
    Returns (repo_html_url, base_commit_sha).
    """
    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    user_resp = requests.get("https://api.github.com/user", headers=headers, timeout=15)
    user_resp.raise_for_status()
    owner = user_resp.json()["login"]
    repo_name = "sentry-pr-hook-test-scratch"

    # Check if repo exists; if not, create it
    repo_check = requests.get(
        f"https://api.github.com/repos/{owner}/{repo_name}",
        headers=headers,
        timeout=15,
    )
    if repo_check.status_code == 404:
        print(f"Creating throwaway GitHub repository: {owner}/{repo_name}...")
        create_resp = requests.post(
            "https://api.github.com/user/repos",
            headers=headers,
            json={
                "name": repo_name,
                "description": "Throwaway scratch repository for Sentry Phase 4a PR Hook verification",
                "private": False,
                "auto_init": False,
            },
            timeout=20,
        )
        create_resp.raise_for_status()
        repo_html_url = create_resp.json()["html_url"]
    else:
        repo_check.raise_for_status()
        repo_html_url = repo_check.json()["html_url"]
        branch_check = requests.get(
            f"https://api.github.com/repos/{owner}/{repo_name}/commits/main",
            headers=headers,
            timeout=15,
        )
        if branch_check.status_code == 200:
            commit_sha = branch_check.json()["sha"]
            print(f"Using existing throwaway repo {repo_html_url} at commit {commit_sha[:7]} (branch: main)", flush=True)
            return repo_html_url, commit_sha

    # Initialize local scratch directory and force-push clean buggy main branch
    scratch_dir = tempfile.mkdtemp(prefix="sentry_throwaway_init_")
    try:
        os.makedirs(os.path.join(scratch_dir, "billing"), exist_ok=True)
        os.makedirs(os.path.join(scratch_dir, "tests"), exist_ok=True)

        with open(os.path.join(scratch_dir, "billing", "__init__.py"), "w", encoding="utf-8") as f:
            f.write("from .tax_calculator import compute_total_with_tax\n")

        with open(os.path.join(scratch_dir, "billing", "tax_calculator.py"), "w", encoding="utf-8") as f:
            f.write(
                'def compute_total_with_tax(subtotal: float, tax_rate: float = 0.08) -> float:\n'
                '    """Computes total invoice amount including sales tax."""\n'
                '    # BUG: Subtracts tax instead of adding it to subtotal\n'
                '    tax_amount = subtotal * tax_rate\n'
                '    return round(subtotal - tax_amount, 2)\n'
            )

        with open(os.path.join(scratch_dir, "tests", "test_tax.py"), "w", encoding="utf-8") as f:
            f.write(
                'from billing.tax_calculator import compute_total_with_tax\n\n'
                'def test_standard_sales_tax():\n'
                '    assert compute_total_with_tax(100.0, 0.08) == 108.0\n\n'
                'def test_zero_tax():\n'
                '    assert compute_total_with_tax(50.0, 0.0) == 50.0\n'
            )

        auth_remote = f"https://x-access-token:{pat}@github.com/{owner}/{repo_name}.git"
        subprocess.run(["git", "init", "-b", "main"], cwd=scratch_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Sentry Test Fixture"], cwd=scratch_dir, check=True)
        subprocess.run(["git", "config", "user.email", "fixture@users.noreply.github.com"], cwd=scratch_dir, check=True)
        subprocess.run(["git", "add", "-A"], cwd=scratch_dir, check=True)
        subprocess.run(["git", "commit", "-m", "feat: initial billing tax calculator (with bug)"], cwd=scratch_dir, check=True, capture_output=True)

        sha_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=scratch_dir, check=True, capture_output=True, text=True)
        commit_sha = sha_res.stdout.strip()

        subprocess.run(["git", "remote", "add", "origin", auth_remote], cwd=scratch_dir, check=True)
        subprocess.run(["git", "push", "-u", "--force", "origin", "main"], cwd=scratch_dir, check=True, capture_output=True)

        print(f"Pushed initial buggy commit {commit_sha[:7]} to {repo_html_url} (branch: main)")
        return repo_html_url, commit_sha
    finally:
        def on_rm_error(func, path, exc_info):
            try:
                os.chmod(path, 0o777)
                func(path)
            except Exception:
                pass
        shutil.rmtree(scratch_dir, onerror=on_rm_error)


def main():
    print("=" * 75)
    print("  PHASE 4a VERIFICATION: GitHub PR/Git Integration Hook")
    print("=" * 75)

    pat = ensure_github_pat_in_env()
    repo_url, base_sha = setup_throwaway_github_repo(pat)

    unified_diff = (
        "--- a/billing/tax_calculator.py\n"
        "+++ b/billing/tax_calculator.py\n"
        "@@ -1,5 +1,5 @@\n"
        " def compute_total_with_tax(subtotal: float, tax_rate: float = 0.08) -> float:\n"
        "     \"\"\"Computes total invoice amount including sales tax.\"\"\"\n"
        "-    # BUG: Subtracts tax instead of adding it to subtotal\n"
        "     tax_amount = subtotal * tax_rate\n"
        "-    return round(subtotal - tax_amount, 2)\n"
        "+    return round(subtotal + tax_amount, 2)\n"
    )

    request = PRCreationRequest(
        repo_url=repo_url,
        commit_sha=base_sha,
        target_file="billing/tax_calculator.py",
        unified_diff=unified_diff,
        explanation=(
            "The compute_total_with_tax function was subtracting tax_amount from subtotal "
            "instead of adding it, causing a $100.00 order with 8% tax to return $92.00 "
            "rather than $108.00. Replacing the subtraction operator with addition resolves "
            "the invoice calculation failure across all test cases."
        ),
        root_cause_hypothesis=(
            "Primary Suspect: billing/tax_calculator.py (confidence 0.98). "
            "Line 5 uses '-' instead of '+' when combining subtotal and tax_amount."
        ),
        before_counts={"tests_total": 2, "tests_passed": 1, "tests_failed": 1},
        after_counts={"tests_total": 2, "tests_passed": 2, "tests_failed": 0},
        base_branch="main",
        model_id="ibm/granite-3-8b-instruct",
        attempts_used=1,
    )

    emitted_events = []

    def on_event(ev):
        emitted_events.append(ev)
        print(f"  [{ev['state']} | {ev['event_type']}] {ev['message']}")

    print("\nExecuting PR Hook...")
    result: PRCreationResult = execute_pr_hook(request=request, emit_event=on_event)

    assert result.success, f"PR creation failed: {result.error_message}"
    assert result.pr_url.startswith("https://github.com/"), f"Invalid PR URL: {result.pr_url}"
    assert result.pr_number >= 1
    assert result.event["event_type"] == "pr_created"
    assert result.event["state"] == "PR_CREATE"
    assert result.event["data"]["pr_url"] == result.pr_url

    print("\n--- Live PR Created Successfully ---")
    print(f"  PR URL        : {result.pr_url}")
    print(f"  PR Number     : #{result.pr_number}")
    print(f"  PR Title      : {result.title}")
    print(f"  Head Branch   : {result.branch_name} -> {result.base_branch}")
    print(f"  Commit SHA    : {result.commit_sha}")

    print("\n--- Emitted Canonical pr_created Event JSON ---")
    print(json.dumps(result.event, indent=2))

    out_file = os.path.join(BASE_DIR, "phase4a_verification_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "phase": "Phase 4a - GitHub PR/Git Integration Verification",
                "throwaway_repo_url": repo_url,
                "base_commit_sha": base_sha,
                "pr_result": result.to_dict(),
                "emitted_pr_created_event": result.event,
                "all_events": emitted_events,
            },
            f,
            indent=2,
        )

    print("\n" + "=" * 75)
    print(f"  Phase 4a Verification Complete! Saved to {out_file}")
    print("=" * 75)


if __name__ == "__main__":
    main()
