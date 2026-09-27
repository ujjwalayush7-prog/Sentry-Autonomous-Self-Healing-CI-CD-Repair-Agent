"""
Hand-Rolled Agent Orchestrator State Machine
States:
  INGEST -> REPRODUCE -> NAVIGATE -> HYPOTHESIZE -> PATCH -> VALIDATE
  -> (loop to PATCH on failure, max 3 attempts) -> PR_CREATE or REPORT_BEST_EFFORT

Every state transition and reasoning step emits a canonical event over WebSocket/callback.
"""

import os
import shutil
import subprocess
import tempfile
import time
import logging
from dataclasses import dataclass, asdict, field
from typing import Any, Callable, Dict, List, Optional

from sandbox import BaseSandbox, get_sandbox, ExecutionResult
from llm import BaseLLMAdapter, get_llm_adapter, SuspectFile, NavigationResult, PatchResult
from orchestrator.events import (
    AgentState,
    EventType,
    make_event,
    state_transition_event,
    reasoning_step_event,
    suspect_ranking_event,
    patch_generated_event,
    validation_result_event,
    error_event,
)
from orchestrator.navigator import navigate, collect_source_files
from orchestrator.patch_applier import apply_patch
from orchestrator.test_runner_parser import parse_test_counts

logger = logging.getLogger(__name__)


@dataclass
class AttemptRecord:
    """Tracks a single patch + validate attempt."""
    attempt: int
    target_file: str
    unified_diff: str
    explanation: str
    patch_applied: bool
    validation_passed: bool
    tests_total: int
    tests_passed: int
    tests_failed: int
    stack_trace: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OrchestratorRunResult:
    """Final structured output of a complete state machine run."""
    fixed: bool
    final_state: str
    repo_url: str
    runtime: str
    test_cmd: str
    model_id: str
    attempts_used: int
    max_attempts: int
    before_counts: Dict[str, int]
    after_counts: Dict[str, int]
    initial_stack_trace: str
    suspects: List[Dict[str, Any]]
    root_cause_hypothesis: str
    final_diff: str
    final_explanation: str
    target_file: str
    attempt_history: List[Dict[str, Any]]
    events: List[Dict[str, Any]]
    duration_seconds: float
    pr_url: Optional[str] = None
    best_effort_report: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SentryOrchestrator:
    """
    Deterministic, debuggable state machine for automated root-cause analysis and repair.
    """

    def __init__(
        self,
        llm_adapter: Optional[BaseLLMAdapter] = None,
        sandbox: Optional[BaseSandbox] = None,
        max_attempts: int = 3,
        emit_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.llm = llm_adapter or get_llm_adapter()
        self.sandbox = sandbox or get_sandbox()
        self.max_attempts = max_attempts
        self.emit_callback = emit_callback
        self.current_state = AgentState.INGEST
        self.events: List[Dict[str, Any]] = []

    def _emit(self, event: Dict[str, Any]) -> None:
        self.events.append(event)
        if self.emit_callback:
            self.emit_callback(event)

    def _transition(self, to_state: AgentState, message: str = "") -> None:
        from_state = self.current_state
        self.current_state = to_state
        self._emit(state_transition_event(from_state, to_state, message))

    def run(
        self,
        repo_url: str,
        test_cmd: str,
        runtime: str,
        commit_sha: Optional[str] = None,
        setup_cmds: Optional[List[str]] = None,
    ) -> OrchestratorRunResult:
        start_time = time.time()
        work_dir = tempfile.mkdtemp(prefix="sentry_orchestrator_")

        before_counts = {"tests_total": 0, "tests_passed": 0, "tests_failed": 0}
        after_counts = {"tests_total": 0, "tests_passed": 0, "tests_failed": 0}
        initial_stack_trace = ""
        suspects: List[SuspectFile] = []
        hypothesis = ""
        final_diff = ""
        final_explanation = ""
        target_file = ""
        attempt_history: List[AttemptRecord] = []
        fixed = False
        best_effort_report = None

        try:
            # =================================================================
            # STATE 1: INGEST
            # =================================================================
            self.current_state = AgentState.INGEST
            self._emit(make_event(
                EventType.STATE_TRANSITION,
                AgentState.INGEST,
                {"from_state": "START", "to_state": AgentState.INGEST.value},
                f"Starting Sentry pipeline on {repo_url} ({runtime})",
            ))

            self._emit(reasoning_step_event(
                AgentState.INGEST, 1,
                f"Cloning repository into isolated working environment...",
                {"repo_url": repo_url, "commit_sha": commit_sha},
            ))

            if os.path.isdir(repo_url):
                shutil.copytree(repo_url, work_dir, dirs_exist_ok=True)
            else:
                clone_res = subprocess.run(
                    ["git", "clone", repo_url, "."],
                    cwd=work_dir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if clone_res.returncode != 0:
                    raise RuntimeError(f"Repository clone failed: {clone_res.stderr}")

            if commit_sha:
                subprocess.run(
                    ["git", "checkout", commit_sha],
                    cwd=work_dir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

            self._emit(reasoning_step_event(
                AgentState.INGEST, 2,
                "Repository ingested and checked out cleanly.",
            ))

            # =================================================================
            # STATE 2: REPRODUCE
            # =================================================================
            self._transition(
                AgentState.REPRODUCE,
                f"Executing test command `{test_cmd}` in sandbox to reproduce failure...",
            )

            repro_res: ExecutionResult = self.sandbox.execute(
                repo_url=work_dir,
                commit_sha=None,
                test_cmd=test_cmd,
                runtime=runtime,
                setup_cmds=setup_cmds,
            )

            before_counts = parse_test_counts(
                repro_res.stdout, repro_res.stderr, repro_res.passed, runtime
            )
            initial_stack_trace = repro_res.stack_trace

            self._emit(reasoning_step_event(
                AgentState.REPRODUCE, 1,
                f"Initial test run finished: {before_counts['tests_passed']}/{before_counts['tests_total']} passed, "
                f"{before_counts['tests_failed']} failed (exit_code={repro_res.exit_code}).",
                {
                    "before_counts": before_counts,
                    "stack_trace": initial_stack_trace,
                    "sandbox_type": repro_res.sandbox_type,
                },
            ))

            if repro_res.passed:
                self._emit(reasoning_step_event(
                    AgentState.REPRODUCE, 2,
                    "Test suite already passes on initial run — no bug to fix.",
                ))
                self._transition(AgentState.DONE, "Pipeline complete (no failure reproduced).")
                return OrchestratorRunResult(
                    fixed=True,
                    final_state=self.current_state.value,
                    repo_url=repo_url,
                    runtime=runtime,
                    test_cmd=test_cmd,
                    model_id=self.llm.get_model_id(),
                    attempts_used=0,
                    max_attempts=self.max_attempts,
                    before_counts=before_counts,
                    after_counts=before_counts,
                    initial_stack_trace="",
                    suspects=[],
                    root_cause_hypothesis="No failure detected.",
                    final_diff="",
                    final_explanation="Tests passed without modification.",
                    target_file="",
                    attempt_history=[],
                    events=self.events,
                    duration_seconds=round(time.time() - start_time, 3),
                )

            # =================================================================
            # STATE 3: NAVIGATE
            # =================================================================
            self._transition(
                AgentState.NAVIGATE,
                "Tracing stack frames and dependency imports to rank suspect root-cause files...",
            )

            nav_result, _ = navigate(
                llm=self.llm,
                stack_trace=initial_stack_trace,
                repo_path=work_dir,
                runtime=runtime,
                emit_event=self._emit,
            )
            suspects = nav_result.suspects

            # =================================================================
            # STATE 4: HYPOTHESIZE
            # =================================================================
            self._transition(
                AgentState.HYPOTHESIZE,
                "Formulating root-cause hypothesis from top suspect files...",
            )

            # Load source code of all ranked suspect files so PATCH has full visibility
            suspect_paths = [s.file_path for s in suspects]
            all_relevant_files = collect_source_files(work_dir, suspect_paths)

            # Also include any other source files in small repos to ensure complete context
            for root, dirs, files in os.walk(work_dir):
                dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", ".pytest_cache"}]
                for f in files:
                    if f.endswith((".py", ".js", ".ts")):
                        full_p = os.path.join(root, f)
                        rel_p = os.path.relpath(full_p, work_dir).replace(os.sep, "/")
                        if rel_p not in all_relevant_files:
                            try:
                                with open(full_p, "r", encoding="utf-8") as fp:
                                    all_relevant_files[rel_p] = fp.read()
                            except Exception:
                                pass

            if suspects:
                top = suspects[0]
                hypothesis = (
                    f"Primary Suspect: {top.file_path} (confidence {top.confidence:.2f}). "
                    f"Reasoning: {top.reasoning} "
                    f"Suspected Defect: {top.suspected_defect}"
                )
            else:
                hypothesis = f"Root cause suspected in files referenced by stack trace:\n{initial_stack_trace}"

            self._emit(reasoning_step_event(
                AgentState.HYPOTHESIZE, 1,
                f"Hypothesis formulated: {hypothesis}",
                {
                    "hypothesis": hypothesis,
                    "files_loaded_for_patch": list(all_relevant_files.keys()),
                },
            ))

            # =================================================================
            # STATE 5 & 6: PATCH <-> VALIDATE LOOP (max 3 attempts)
            # =================================================================
            current_stack_trace = initial_stack_trace
            current_hypothesis = hypothesis

            for attempt in range(1, self.max_attempts + 1):
                self._transition(
                    AgentState.PATCH,
                    f"Generating minimal surgical patch (Attempt {attempt} of {self.max_attempts})...",
                )

                # Refresh file contents from clean working directory
                fresh_contents = {}
                for rel_p in all_relevant_files:
                    full_p = os.path.join(work_dir, rel_p.replace("/", os.sep))
                    if os.path.exists(full_p):
                        with open(full_p, "r", encoding="utf-8") as fp:
                            fresh_contents[rel_p] = fp.read()

                patch_res: PatchResult = self.llm.generate_patch(
                    suspect_files=suspects,
                    file_contents=fresh_contents,
                    stack_trace=current_stack_trace,
                    hypothesis=current_hypothesis,
                    runtime=runtime,
                )

                target_file = patch_res.target_file
                raw_diff = patch_res.unified_diff
                explanation = patch_res.explanation

                # Apply the patch to work_dir
                applied_ok, apply_msg = apply_patch(work_dir, target_file, raw_diff)

                # Capture canonical git diff from the modified repo
                git_diff_res = subprocess.run(
                    ["git", "diff"],
                    cwd=work_dir,
                    capture_output=True,
                    text=True,
                )
                canonical_diff = git_diff_res.stdout.strip() or raw_diff

                self._emit(patch_generated_event(
                    target_file=target_file,
                    unified_diff=canonical_diff,
                    explanation=explanation,
                    attempt=attempt,
                    model_id=patch_res.model_id,
                ))

                self._emit(reasoning_step_event(
                    AgentState.PATCH, attempt,
                    f"Patch application status: {apply_msg}",
                    {"applied": applied_ok, "explanation": explanation},
                ))

                # Transition to VALIDATE
                self._transition(
                    AgentState.VALIDATE,
                    f"Validating patched codebase against full test suite (Attempt {attempt})...",
                )

                val_res: ExecutionResult = self.sandbox.execute(
                    repo_url=work_dir,
                    commit_sha=None,
                    test_cmd=test_cmd,
                    runtime=runtime,
                    setup_cmds=setup_cmds,
                )

                val_counts = parse_test_counts(
                    val_res.stdout, val_res.stderr, val_res.passed, runtime
                )

                self._emit(validation_result_event(
                    passed=val_res.passed,
                    tests_passed=val_counts["tests_passed"],
                    tests_failed=val_counts["tests_failed"],
                    tests_total=val_counts["tests_total"],
                    attempt=attempt,
                    stdout_summary=val_res.stdout[-500:] if val_res.stdout else "",
                    before_counts=before_counts,
                    after_counts=val_counts,
                ))

                attempt_record = AttemptRecord(
                    attempt=attempt,
                    target_file=target_file,
                    unified_diff=canonical_diff,
                    explanation=explanation,
                    patch_applied=applied_ok,
                    validation_passed=val_res.passed,
                    tests_total=val_counts["tests_total"],
                    tests_passed=val_counts["tests_passed"],
                    tests_failed=val_counts["tests_failed"],
                    stack_trace=val_res.stack_trace,
                )
                attempt_history.append(attempt_record)

                if val_res.passed and val_counts["tests_failed"] == 0:
                    fixed = True
                    after_counts = val_counts
                    final_diff = canonical_diff
                    final_explanation = explanation
                    self._emit(reasoning_step_event(
                        AgentState.VALIDATE, attempt,
                        f"RED -> GREEN achieved on attempt {attempt}! "
                        f"Before: {before_counts['tests_passed']}/{before_counts['tests_total']} passed. "
                        f"After: {after_counts['tests_passed']}/{after_counts['tests_total']} passed.",
                        {"before_counts": before_counts, "after_counts": after_counts},
                    ))
                    break
                else:
                    # Revert working tree for clean next attempt
                    subprocess.run(["git", "checkout", "--", "."], cwd=work_dir, capture_output=True)
                    current_stack_trace = val_res.stack_trace or initial_stack_trace
                    current_hypothesis = (
                        f"{hypothesis}\n\n"
                        f"Previous Attempt {attempt} failed validation with diff:\n{canonical_diff}\n"
                        f"Validation failure output:\n{current_stack_trace}\n"
                        f"Adjust the fix to ensure all tests pass."
                    )
                    self._emit(reasoning_step_event(
                        AgentState.VALIDATE, attempt,
                        f"Attempt {attempt} did not pass all tests "
                        f"({val_counts['tests_passed']}/{val_counts['tests_total']} passed). "
                        f"Reverting workspace for next attempt.",
                    ))

            # =================================================================
            # TERMINAL STATE: PR_CREATE or REPORT_BEST_EFFORT
            # =================================================================
            pr_url = None
            if fixed:
                self._transition(
                    AgentState.PR_CREATE,
                    "All tests green! Ready for Pull Request creation.",
                )
                if "github.com" in repo_url.lower():
                    from git_integration import PRCreationRequest, execute_pr_hook
                    pr_req = PRCreationRequest(
                        repo_url=repo_url,
                        commit_sha=commit_sha,
                        target_file=target_file,
                        unified_diff=final_diff,
                        explanation=final_explanation,
                        root_cause_hypothesis=hypothesis,
                        before_counts=before_counts,
                        after_counts=after_counts,
                        model_id=self.llm.get_model_id(),
                        attempts_used=len(attempt_history),
                    )
                    pr_res = execute_pr_hook(request=pr_req, emit_event=self._emit)
                    if pr_res.success:
                        pr_url = pr_res.pr_url
                else:
                    self._emit(reasoning_step_event(
                        AgentState.PR_CREATE, 1,
                        "Local repository path detected — skipping remote GitHub PR creation.",
                        {"repo_url": repo_url},
                    ))
            else:
                self._transition(
                    AgentState.REPORT_BEST_EFFORT,
                    f"Exhausted all {self.max_attempts} repair attempts without full test suite pass. "
                    f"Compiling best-effort diagnostic report (no false success claimed).",
                )
                after_counts = (
                    {
                        "tests_total": attempt_history[-1].tests_total,
                        "tests_passed": attempt_history[-1].tests_passed,
                        "tests_failed": attempt_history[-1].tests_failed,
                    }
                    if attempt_history
                    else before_counts
                )
                best_effort_report = {
                    "status": "UNRESOLVED_AFTER_MAX_ATTEMPTS",
                    "attempts_exhausted": len(attempt_history),
                    "best_hypothesis": hypothesis,
                    "top_suspects": [s.to_dict() for s in suspects],
                    "attempt_history": [a.to_dict() for a in attempt_history],
                }
                self._emit(make_event(
                    EventType.BEST_EFFORT_REPORT,
                    AgentState.REPORT_BEST_EFFORT,
                    best_effort_report,
                    "Best-effort diagnostic trail compiled after 3 unsuccessful attempts.",
                ))

        except Exception as e:
            logger.exception("Orchestrator encountered an error")
            self._emit(error_event(self.current_state, str(e)))
            self._transition(AgentState.ERROR, f"Pipeline aborted: {e}")
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

        duration = round(time.time() - start_time, 3)
        return OrchestratorRunResult(
            fixed=fixed,
            final_state=self.current_state.value,
            repo_url=repo_url,
            runtime=runtime,
            test_cmd=test_cmd,
            model_id=self.llm.get_model_id(),
            attempts_used=len(attempt_history),
            max_attempts=self.max_attempts,
            before_counts=before_counts,
            after_counts=after_counts,
            initial_stack_trace=initial_stack_trace,
            suspects=[s.to_dict() for s in suspects],
            root_cause_hypothesis=hypothesis,
            final_diff=final_diff,
            final_explanation=final_explanation,
            target_file=target_file,
            attempt_history=[a.to_dict() for a in attempt_history],
            events=self.events,
            duration_seconds=duration,
            pr_url=pr_url,
            best_effort_report=best_effort_report,
        )
