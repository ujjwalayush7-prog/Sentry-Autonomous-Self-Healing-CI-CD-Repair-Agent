"""
Git/Repo Hook Execution Engine
Implements:
1. Clone + checkout (given repo_url + commit_sha)
2. Apply validated patch via orchestrator.patch_applier.apply_patch
3. Create branch, commit with auto-generated explanation
4. Push branch and open PR via GitHub REST API using GITHUB_PAT
5. Emit canonical pr_created event
"""

import os
import re
import shutil
import subprocess
import tempfile
import time
import logging
from typing import Any, Callable, Dict, Optional

from orchestrator.patch_applier import apply_patch
from orchestrator.events import (
    AgentState,
    reasoning_step_event,
    pr_created_event,
    error_event,
)
from .models import PRCreationRequest, PRCreationResult
from .github_client import (
    GitHubPRClient,
    parse_github_repo,
    build_pr_title,
    build_pr_body,
)

logger = logging.getLogger(__name__)


def _sanitize_branch_slug(target_file: str) -> str:
    base = os.path.splitext(os.path.basename(target_file.replace("\\", "/")))[0]
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", base).strip("-").lower()
    return slug or "patch"


def execute_pr_hook(
    request: PRCreationRequest,
    emit_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    github_pat: Optional[str] = None,
) -> PRCreationResult:
    """
    Executes the end-to-end Git clone -> patch -> branch -> commit -> push -> GitHub PR flow.
    """
    def _emit(ev: Dict[str, Any]) -> None:
        if emit_event:
            emit_event(ev)

    work_dir = tempfile.mkdtemp(prefix="sentry_pr_hook_")

    try:
        client = GitHubPRClient(pat=github_pat)
        owner, repo = parse_github_repo(request.repo_url)
        repo_full_name = f"{owner}/{repo}"

        base_branch = request.base_branch or client.get_default_branch(owner, repo)
        auth_clone_url = f"https://x-access-token:{client.pat}@github.com/{owner}/{repo}.git"
        git_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}

        # 1. Clone repository
        _emit(reasoning_step_event(
            AgentState.PR_CREATE, 1,
            f"Cloning {repo_full_name} to prepare Pull Request branch...",
            {"repo_full_name": repo_full_name, "base_branch": base_branch},
        ))

        clone_res = subprocess.run(
            ["git", "-c", "credential.helper=", "clone", auth_clone_url, "."],
            cwd=work_dir,
            env=git_env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if clone_res.returncode != 0:
            raise RuntimeError(f"git clone failed for {repo_full_name}: {clone_res.stderr}")

        # Configure git author identity for commit
        subprocess.run(["git", "config", "user.name", "Sentry CI/CD Agent"], cwd=work_dir, check=True)
        subprocess.run(["git", "config", "user.email", "sentry-bot@users.noreply.github.com"], cwd=work_dir, check=True)

        # Checkout specific commit SHA if provided
        if request.commit_sha:
            co_res = subprocess.run(
                ["git", "checkout", request.commit_sha],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if co_res.returncode != 0:
                logger.warning(f"Checkout of {request.commit_sha} returned non-zero: {co_res.stderr}")

        # 2. Create a new fix branch
        slug = _sanitize_branch_slug(request.target_file)
        timestamp_suffix = int(time.time())
        branch_name = f"sentry/fix-{slug}-{timestamp_suffix}"

        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=work_dir,
            capture_output=True,
            text=True,
            check=True,
        )

        _emit(reasoning_step_event(
            AgentState.PR_CREATE, 2,
            f"Created fix branch `{branch_name}` and applying validated patch to `{request.target_file}`...",
            {"branch_name": branch_name, "target_file": request.target_file},
        ))

        # 3. Apply the validated patch (reusing Phase 3 patch_applier)
        applied_ok, apply_msg = apply_patch(
            repo_path=work_dir,
            target_file=request.target_file,
            unified_diff=request.unified_diff,
        )
        if not applied_ok:
            raise RuntimeError(f"Failed to apply validated patch during PR hook: {apply_msg}")

        # 4. Stage & commit with message derived from auto-generated explanation
        pr_title = build_pr_title(request.target_file, request.explanation)
        commit_message = f"{pr_title}\n\n{request.explanation.strip()}"

        subprocess.run(["git", "add", "-A"], cwd=work_dir, check=True)
        commit_res = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=work_dir,
            capture_output=True,
            text=True,
        )
        if commit_res.returncode != 0:
            raise RuntimeError(f"git commit failed: {commit_res.stderr or commit_res.stdout}")

        sha_res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=work_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        head_commit_sha = sha_res.stdout.strip()

        # 5. Push branch to GitHub origin
        _emit(reasoning_step_event(
            AgentState.PR_CREATE, 3,
            f"Committed fix ({head_commit_sha[:7]}). Pushing branch `{branch_name}` to GitHub...",
            {"commit_sha": head_commit_sha, "branch_name": branch_name},
        ))

        push_res = subprocess.run(
            ["git", "-c", "credential.helper=", "push", "-u", "origin", branch_name],
            cwd=work_dir,
            env=git_env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if push_res.returncode != 0:
            raise RuntimeError(f"git push failed: {push_res.stderr}")

        # 6. Open Pull Request via GitHub REST API
        pr_body = build_pr_body(
            target_file=request.target_file,
            explanation=request.explanation,
            root_cause_hypothesis=request.root_cause_hypothesis,
            before_counts=request.before_counts,
            after_counts=request.after_counts,
            unified_diff=request.unified_diff,
            model_id=request.model_id,
            attempts_used=request.attempts_used,
        )

        pr_data = client.create_pull_request(
            owner=owner,
            repo=repo,
            title=pr_title,
            body=pr_body,
            head_branch=branch_name,
            base_branch=base_branch,
        )

        pr_url = pr_data["html_url"]
        pr_number = pr_data["number"]

        # 7. Emit canonical pr_created event
        canonical_ev = pr_created_event(
            pr_url=pr_url,
            pr_number=pr_number,
            title=pr_title,
            branch_name=branch_name,
            base_branch=base_branch,
            commit_sha=head_commit_sha,
            repo_full_name=repo_full_name,
            body=pr_body,
        )
        _emit(canonical_ev)

        return PRCreationResult(
            success=True,
            pr_url=pr_url,
            pr_number=pr_number,
            title=pr_title,
            body=pr_body,
            branch_name=branch_name,
            base_branch=base_branch,
            commit_sha=head_commit_sha,
            repo_full_name=repo_full_name,
            event=canonical_ev,
        )

    except Exception as e:
        logger.exception("PR Hook execution failed")
        err_ev = error_event(AgentState.PR_CREATE, str(e), error_type="pr_creation_error")
        _emit(err_ev)
        return PRCreationResult(
            success=False,
            pr_url="",
            pr_number=0,
            title="",
            body="",
            branch_name="",
            base_branch=request.base_branch or "main",
            commit_sha="",
            repo_full_name=request.repo_url,
            event=err_ev,
            error_message=str(e),
        )
    finally:
        try:
            def on_rm_error(func, path, exc_info):
                try:
                    os.chmod(path, 0o777)
                    func(path)
                except Exception:
                    pass
            shutil.rmtree(work_dir, onerror=on_rm_error)
        except Exception:
            pass
