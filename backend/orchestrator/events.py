"""
Orchestrator Event Protocol
Defines the JSON event shapes that stream over WebSocket to the frontend.
Every state transition and reasoning step emits one of these events.
This is the CANONICAL event format — frontend renders from this directly.
"""

import time
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional
from enum import Enum


class AgentState(str, Enum):
    """State machine states for the orchestrator."""
    INGEST = "INGEST"
    REPRODUCE = "REPRODUCE"
    NAVIGATE = "NAVIGATE"
    HYPOTHESIZE = "HYPOTHESIZE"
    PATCH = "PATCH"
    VALIDATE = "VALIDATE"
    PR_CREATE = "PR_CREATE"
    REPORT_BEST_EFFORT = "REPORT_BEST_EFFORT"
    DONE = "DONE"
    ERROR = "ERROR"


class EventType(str, Enum):
    """Types of events emitted by the orchestrator."""
    STATE_TRANSITION = "state_transition"
    REASONING_STEP = "reasoning_step"
    SUSPECT_RANKING = "suspect_ranking"
    PATCH_GENERATED = "patch_generated"
    VALIDATION_RESULT = "validation_result"
    PR_CREATED = "pr_created"
    BEST_EFFORT_REPORT = "best_effort_report"
    ERROR = "error"
    LOG = "log"


def make_event(
    event_type: EventType,
    state: AgentState,
    data: Dict[str, Any],
    message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a canonical event dict for WebSocket streaming.

    This is THE event shape the frontend consumes — every state transition,
    reasoning trace, suspect ranking, diff, and validation result uses this
    same envelope.
    """
    return {
        "event_type": event_type.value,
        "state": state.value,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "message": message or "",
        "data": data,
    }


def state_transition_event(
    from_state: AgentState,
    to_state: AgentState,
    message: str = "",
) -> Dict[str, Any]:
    """Emitted when the state machine transitions between states."""
    return make_event(
        EventType.STATE_TRANSITION,
        to_state,
        {"from_state": from_state.value, "to_state": to_state.value},
        message or f"Transitioning from {from_state.value} to {to_state.value}",
    )


def reasoning_step_event(
    state: AgentState,
    step_number: int,
    description: str,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Emitted for each human-legible reasoning step within a state."""
    return make_event(
        EventType.REASONING_STEP,
        state,
        {
            "step_number": step_number,
            "description": description,
            **(details or {}),
        },
        description,
    )


def suspect_ranking_event(
    suspects: List[Dict[str, Any]],
    reasoning_trace: str,
    files_analyzed: int,
    model_id: str,
) -> Dict[str, Any]:
    """Emitted when NAVIGATE produces suspect file rankings."""
    return make_event(
        EventType.SUSPECT_RANKING,
        AgentState.NAVIGATE,
        {
            "suspects": suspects,
            "reasoning_trace": reasoning_trace,
            "files_analyzed": files_analyzed,
            "model_id": model_id,
        },
        f"Navigation complete: {len(suspects)} suspect files ranked using {model_id}",
    )


def patch_generated_event(
    target_file: str,
    unified_diff: str,
    explanation: str,
    attempt: int,
    model_id: str,
) -> Dict[str, Any]:
    """Emitted when PATCH produces a diff."""
    return make_event(
        EventType.PATCH_GENERATED,
        AgentState.PATCH,
        {
            "target_file": target_file,
            "unified_diff": unified_diff,
            "explanation": explanation,
            "attempt": attempt,
            "model_id": model_id,
        },
        f"Patch generated for {target_file} (attempt {attempt})",
    )


def validation_result_event(
    passed: bool,
    tests_passed: int,
    tests_failed: int,
    tests_total: int,
    attempt: int,
    stdout_summary: str = "",
    before_counts: Optional[Dict[str, int]] = None,
    after_counts: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Emitted when VALIDATE finishes running the test suite."""
    computed_after = after_counts or {
        "tests_total": tests_total,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
    }
    payload: Dict[str, Any] = {
        "passed": passed,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "tests_total": tests_total,
        "attempt": attempt,
        "stdout_summary": stdout_summary,
        "after_counts": computed_after,
    }
    if before_counts is not None:
        payload["before_counts"] = before_counts

    return make_event(
        EventType.VALIDATION_RESULT,
        AgentState.VALIDATE,
        payload,
        f"Validation {'PASSED' if passed else 'FAILED'}: {tests_passed}/{tests_total} tests passed (attempt {attempt})",
    )


def pr_created_event(
    pr_url: str,
    pr_number: int,
    title: str,
    branch_name: str,
    base_branch: str,
    commit_sha: str,
    repo_full_name: str,
    body: str = "",
) -> Dict[str, Any]:
    """Emitted when PR_CREATE successfully opens a Pull Request on GitHub."""
    return make_event(
        EventType.PR_CREATED,
        AgentState.PR_CREATE,
        {
            "pr_url": pr_url,
            "pr_number": pr_number,
            "title": title,
            "branch_name": branch_name,
            "base_branch": base_branch,
            "commit_sha": commit_sha,
            "repo_full_name": repo_full_name,
            "body": body,
        },
        f"Pull Request #{pr_number} opened: {pr_url}",
    )


def error_event(
    state: AgentState,
    error_message: str,
    error_type: str = "unknown",
) -> Dict[str, Any]:
    """Emitted on unrecoverable errors."""
    return make_event(
        EventType.ERROR,
        state,
        {"error_message": error_message, "error_type": error_type},
        f"Error in {state.value}: {error_message}",
    )
