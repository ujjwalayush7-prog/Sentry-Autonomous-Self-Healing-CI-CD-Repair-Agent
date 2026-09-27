"""
Sandbox Execution Layer - Local Isolated Process Sandbox
Executes test commands in an ephemeral, isolated directory.
Used as a reliable fallback when Docker daemon is not running on the host system.
"""

import os
import sys
import shutil
import subprocess
import tempfile
import time
import logging
from typing import List, Optional

from .base import BaseSandbox
from .models import ExecutionResult
from .parsers import extract_stack_trace

logger = logging.getLogger(__name__)


class LocalSandbox(BaseSandbox):
    """
    Executes tests inside an ephemeral workspace directory on the host.
    Provides identical interfaces, outputs, and cleanup guarantees as DockerSandbox.
    """

    @classmethod
    def is_available(cls) -> bool:
        """Local sandbox is always available as long as git and runtimes are on PATH."""
        return True

    def execute(
        self,
        repo_url: str,
        commit_sha: Optional[str],
        test_cmd: str,
        runtime: str,
        setup_cmds: Optional[List[str]] = None,
        timeout_seconds: int = 120,
    ) -> ExecutionResult:
        start_time = time.time()
        temp_dir = tempfile.mkdtemp(prefix="sentry_sandbox_")

        stdout = ""
        stderr = ""
        exit_code = 1

        try:
            # 1. Prepare environment with Python scripts and current PATH
            env = os.environ.copy()
            import sysconfig
            extra_paths = []
            try:
                user_scripts = sysconfig.get_path("scripts", "nt_user")
                if os.path.isdir(user_scripts):
                    extra_paths.append(user_scripts)
            except Exception:
                pass
            try:
                sys_scripts = sysconfig.get_path("scripts")
                if os.path.isdir(sys_scripts):
                    extra_paths.append(sys_scripts)
            except Exception:
                pass
            if extra_paths:
                env["PATH"] = os.pathsep.join(extra_paths) + os.pathsep + env.get("PATH", "")

            # 2. Clone or copy repo into ephemeral directory
            if os.path.isdir(repo_url):
                # Copy local repo files
                shutil.copytree(repo_url, temp_dir, dirs_exist_ok=True)
            else:
                clone_res = subprocess.run(
                    ["git", "clone", repo_url, "."],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if clone_res.returncode != 0:
                    raise RuntimeError(f"Git clone failed: {clone_res.stderr}")

            # 2. Checkout target commit if specified
            if commit_sha:
                co_res = subprocess.run(
                    ["git", "checkout", commit_sha],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if co_res.returncode != 0:
                    logger.warning(f"Could not checkout commit {commit_sha}: {co_res.stderr}")

            # 3. Execute setup commands if any
            if setup_cmds:
                for sc in setup_cmds:
                    setup_res = subprocess.run(
                        sc,
                        cwd=temp_dir,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=120,
                        env=env,
                    )
                    if setup_res.returncode != 0:
                        logger.warning(f"Setup command '{sc}' exited with {setup_res.returncode}: {setup_res.stderr}")

            # 4. Normalize command if needed (e.g. pytest -> python -m pytest)
            effective_cmd = test_cmd
            if runtime.lower() in ("python", "py") and test_cmd.strip().startswith("pytest"):
                # Ensure it invokes the current Python interpreter if pytest standalone isn't resolved
                effective_cmd = f'"{sys.executable}" -m ' + test_cmd.strip()

            # 5. Execute test command
            test_res = subprocess.run(
                effective_cmd,
                cwd=temp_dir,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=env,
            )
            exit_code = test_res.returncode
            stdout = test_res.stdout
            stderr = test_res.stderr

        except subprocess.TimeoutExpired:
            exit_code = 124
            stderr = f"Execution timed out after {timeout_seconds} seconds."
        except Exception as e:
            exit_code = 1
            stderr = f"Local sandbox execution error: {str(e)}"
        finally:
            # Clean up ephemeral directory
            try:
                # On Windows, git files might have read-only flags
                def on_rm_error(func, path, exc_info):
                    try:
                        os.chmod(path, 0o777)
                        func(path)
                    except Exception:
                        pass
                shutil.rmtree(temp_dir, onerror=on_rm_error)
            except Exception as e:
                logger.warning(f"Failed to remove sandbox temp dir {temp_dir}: {e}")

        duration = time.time() - start_time
        passed = (exit_code == 0)
        stack_trace = "" if passed else extract_stack_trace(stdout, stderr, runtime)

        return ExecutionResult(
            passed=passed,
            stdout=stdout,
            stderr=stderr,
            stack_trace=stack_trace,
            exit_code=exit_code,
            duration_seconds=round(duration, 3),
            runtime=runtime,
            sandbox_type="local",
            commit_sha=commit_sha,
            repo_url=repo_url,
            command_executed=test_cmd,
        )
