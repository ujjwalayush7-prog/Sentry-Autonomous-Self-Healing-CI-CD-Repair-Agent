"""
Sandbox Execution Layer - Docker Container Sandbox
Executes test commands inside ephemeral Docker containers (python:3.11-slim / node:20-slim).
Hardened for zero-dependency containers (handles git on host, mounts workspace to container).
"""

import time
import os
import shutil
import subprocess
import tempfile
import logging
from typing import List, Optional

from .base import BaseSandbox
from .models import ExecutionResult
from .parsers import extract_stack_trace

logger = logging.getLogger(__name__)

try:
    import docker
    from docker.errors import DockerException, APIError, ImageNotFound
    DOCKER_INSTALLED = True
except ImportError:
    DOCKER_INSTALLED = False


RUNTIME_IMAGES = {
    "python": "python:3.11-slim",
    "py": "python:3.11-slim",
    "node": "node:20-slim",
    "nodejs": "node:20-slim",
    "js": "node:20-slim",
    "ts": "node:20-slim",
}


def normalize_docker_path(path: str) -> str:
    """Normalizes host path for Docker volume bind mounts across platforms."""
    abs_path = os.path.abspath(path)
    # Convert Windows backslashes to forward slashes for Docker API compatibility
    return abs_path.replace("\\", "/")


class DockerSandbox(BaseSandbox):
    """
    Executes tests inside ephemeral Docker containers.
    Prepares workspace on host to avoid missing tools (e.g. git in slim images),
    mounts isolated workspace into container, executes test_cmd, and cleans up.
    """

    def __init__(self, client=None):
        if not DOCKER_INSTALLED:
            raise RuntimeError("docker Python package is not installed.")
        if client:
            self.client = client
        else:
            try:
                self.client = docker.from_env()
                self.client.ping()
            except Exception as e:
                raise RuntimeError(f"Docker daemon is not accessible: {e}")

    @classmethod
    def is_available(cls) -> bool:
        """Check if Docker daemon is running and reachable."""
        if not DOCKER_INSTALLED:
            return False
        try:
            client = docker.from_env()
            client.ping()
            return True
        except Exception:
            return False

    def execute(
        self,
        repo_url: str,
        commit_sha: Optional[str],
        test_cmd: str,
        runtime: str,
        setup_cmds: Optional[List[str]] = None,
        timeout_seconds: int = 120,
    ) -> ExecutionResult:
        image = RUNTIME_IMAGES.get(runtime.lower(), "python:3.11-slim")
        start_time = time.time()
        container = None
        temp_dir = tempfile.mkdtemp(prefix="sentry_docker_ws_")

        stdout = ""
        stderr = ""
        exit_code = 1

        try:
            # 1. Prepare workspace on host (cloning/checkout on host guarantees git is available)
            if os.path.isdir(repo_url):
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
                    raise RuntimeError(f"Git clone failed on host: {clone_res.stderr}")

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

            # 2. Ensure container runtime image exists
            try:
                self.client.images.get(image)
            except ImageNotFound:
                logger.info(f"Pulling Docker image: {image}...")
                self.client.images.pull(image)

            # 3. Mount ephemeral workspace directory into container at /workspace
            docker_mount_path = normalize_docker_path(temp_dir)
            volumes = {
                docker_mount_path: {"bind": "/workspace", "mode": "rw"}
            }

            # 4. Construct container execution script
            script_lines = [
                "cd /workspace",
            ]
            if setup_cmds:
                for sc in setup_cmds:
                    script_lines.append(sc)

            script_lines.append(f"{test_cmd}")
            script_lines.append("exit $?")
            full_script = "\n".join(script_lines)

            # 5. Create and run ephemeral container
            container = self.client.containers.create(
                image=image,
                command=["sh", "-c", full_script],
                volumes=volumes,
                working_dir="/workspace",
                network_mode="bridge",
            )
            container.start()

            # 6. Wait with timeout
            result = container.wait(timeout=timeout_seconds)
            exit_code = result.get("StatusCode", 1)

            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

        except Exception as e:
            exit_code = 1
            stderr = f"Docker sandbox execution error: {str(e)}"
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
            # Clean up host temp directory
            try:
                def on_rm_error(func, path, exc_info):
                    try:
                        os.chmod(path, 0o777)
                        func(path)
                    except Exception:
                        pass
                shutil.rmtree(temp_dir, onerror=on_rm_error)
            except Exception as e:
                logger.warning(f"Failed to remove temp dir {temp_dir}: {e}")

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
            sandbox_type="docker",
            commit_sha=commit_sha,
            repo_url=repo_url,
            command_executed=test_cmd,
        )
