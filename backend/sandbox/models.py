"""
Sandbox Execution Layer - Result Models
Structured data models for isolated sandbox execution results.
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class ExecutionResult:
    """Structured result returned by any sandbox implementation."""
    passed: bool
    stdout: str
    stderr: str
    stack_trace: str
    exit_code: int
    duration_seconds: float
    runtime: str              # 'python' | 'node'
    sandbox_type: str         # 'docker' | 'local'
    commit_sha: Optional[str] = None
    repo_url: Optional[str] = None
    command_executed: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to serializable dictionary."""
        return asdict(self)
