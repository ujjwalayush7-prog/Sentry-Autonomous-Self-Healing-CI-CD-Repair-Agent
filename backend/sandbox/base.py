"""
Sandbox Execution Layer - Base Interface
Abstract base class for all sandbox implementations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from .models import ExecutionResult


class BaseSandbox(ABC):
    """
    Abstract interface for executing code in an isolated environment.
    Guarantees consistent input arguments and structured ExecutionResult output.
    """

    @abstractmethod
    def execute(
        self,
        repo_url: str,
        commit_sha: Optional[str],
        test_cmd: str,
        runtime: str,
        setup_cmds: Optional[List[str]] = None,
        timeout_seconds: int = 120,
    ) -> ExecutionResult:
        """
        Executes a test command against a specific commit in an isolated sandbox.

        Args:
            repo_url: Git clone URL or local directory path.
            commit_sha: Commit SHA to checkout (or None for default branch / current HEAD).
            test_cmd: Command to execute (e.g. 'pytest', 'npm test').
            runtime: Runtime identifier ('python' or 'node').
            setup_cmds: Optional list of commands to run before the test (e.g. dependency install).
            timeout_seconds: Max execution time before aborting.

        Returns:
            ExecutionResult containing passed status, stdout, stderr, and extracted stack trace.
        """
        pass

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Returns True if the underlying runtime (e.g., Docker daemon) is accessible."""
        pass
