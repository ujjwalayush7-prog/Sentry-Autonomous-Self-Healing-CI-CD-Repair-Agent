"""
LLM Adapter Layer - Base Interface
Thin abstraction so the model/endpoint can be swapped without touching orchestrator logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional


@dataclass
class SuspectFile:
    """A single file suspected to contain the root cause."""
    rank: int
    file_path: str
    confidence: float          # 0.0 to 1.0
    reasoning: str             # Why this file is suspected
    suspected_defect: str      # What the defect would need to be
    relevant_lines: Optional[str] = None  # Line range hint, e.g. "10-15"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NavigationResult:
    """Complete output from a navigation LLM call."""
    suspects: List[SuspectFile]
    reasoning_trace: str       # Full chain-of-thought from the model
    files_analyzed: int
    model_id: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["suspects"] = [s.to_dict() for s in self.suspects]
        return d


@dataclass
class PatchResult:
    """Output from a patch-generation LLM call."""
    unified_diff: str
    explanation: str           # One-paragraph plain-English explanation
    target_file: str
    model_id: str
    confidence: float = 0.0
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BaseLLMAdapter(ABC):
    """
    Abstract interface for LLM calls used by the orchestrator.
    Two call types: navigation and patch generation.
    """

    @abstractmethod
    def navigate(
        self,
        stack_trace: str,
        file_tree: str,
        file_contents: Dict[str, str],
        runtime: str,
    ) -> NavigationResult:
        """
        Navigation call: Given a stack trace, repo file tree, and relevant file contents,
        produce a ranked list of suspect files with reasoning.
        """
        pass

    @abstractmethod
    def generate_patch(
        self,
        suspect_files: List[SuspectFile],
        file_contents: Dict[str, str],
        stack_trace: str,
        hypothesis: str,
        runtime: str,
    ) -> PatchResult:
        """
        Patch call: Given suspect files and a root-cause hypothesis,
        produce a minimal unified diff and plain-English explanation.
        """
        pass

    @abstractmethod
    def get_model_id(self) -> str:
        """Returns the identifier of the underlying model."""
        pass
