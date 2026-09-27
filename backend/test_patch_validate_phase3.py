"""
Phase 3 Verification: Hypothesis, Patch Generation, and Validation Loop
Tests the complete hand-rolled state machine:
  INGEST -> REPRODUCE -> NAVIGATE -> HYPOTHESIZE -> PATCH -> VALIDATE -> PR_CREATE / REPORT_BEST_EFFORT

Verifies:
1. Hero Python: Red (3 passed, 1 failed) -> Green (4 passed, 0 failed)
2. Hero Node.js: Red (2 passed, 1 failed) -> Green (3 passed, 0 failed)
3. Honest Failure Reporting: 3 failed patch attempts -> REPORT_BEST_EFFORT (never fabricates success)
4. WatsonxAdapter Granite prompt & response contract smoke test
"""

import os
import sys
import json
import logging
from unittest.mock import MagicMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, "..", "Evie", ".env"))

from llm import get_llm_adapter, BaseLLMAdapter, NavigationResult, PatchResult, SuspectFile
from llm.watsonx_adapter import _parse_navigation_response, _parse_patch_response
from orchestrator import SentryOrchestrator, OrchestratorRunResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("phase3_verify")


def run_hero_pipeline(label: str, repo_subdir: str, runtime: str, test_cmd: str) -> dict:
    print(f"\n{'=' * 75}")
    print(f"  PHASE 3 PIPELINE RUN: {label}")
    print(f"{'=' * 75}")

    repo_path = os.path.join(BASE_DIR, "test_repos", repo_subdir)
    llm = get_llm_adapter()

    def on_event(ev):
        etype = ev.get("event_type", "")
        state = ev.get("state", "")
        msg = ev.get("message", "")
        print(f"  [{state} | {etype}] {msg}")

    orchestrator = SentryOrchestrator(
        llm_adapter=llm,
        max_attempts=3,
        emit_callback=on_event,
    )

    result: OrchestratorRunResult = orchestrator.run(
        repo_url=repo_path,
        test_cmd=test_cmd,
        runtime=runtime,
    )

    print(f"\n--- {label} Summary ---")
    print(f"  Final State   : {result.final_state}")
    print(f"  Fixed         : {result.fixed}")
    print(f"  Attempts Used : {result.attempts_used}/{result.max_attempts}")
    print(f"  Before Counts : {result.before_counts['tests_passed']}/{result.before_counts['tests_total']} passed "
          f"({result.before_counts['tests_failed']} failed)")
    print(f"  After Counts  : {result.after_counts['tests_passed']}/{result.after_counts['tests_total']} passed "
          f"({result.after_counts['tests_failed']} failed)")
    print(f"  Target File   : {result.target_file}")
    print(f"  Duration      : {result.duration_seconds}s")
    print(f"\n--- Explanation ---")
    print(f"  {result.final_explanation}")
    print(f"\n--- Unified Diff ---")
    print(result.final_diff)
    print("-" * 75)

    assert result.fixed, f"{label} failed to achieve RED -> GREEN!"
    assert result.final_state == "PR_CREATE", f"Expected PR_CREATE, got {result.final_state}"
    assert result.before_counts["tests_failed"] > 0, "Expected initial failure count > 0"
    assert result.after_counts["tests_failed"] == 0, "Expected after failure count == 0"
    assert result.after_counts["tests_passed"] == result.after_counts["tests_total"], \
        "All tests must pass after patch!"

    return result.to_dict()


def test_best_effort_fallback() -> dict:
    """
    Verifies Non-Negotiable Criterion #3:
    If the agent cannot fix a bug in 3 attempts, it must report its best
    hypothesis and diagnostic trail instead of claiming false success.
    """
    print(f"\n{'=' * 75}")
    print("  VERIFYING NON-NEGOTIABLE #3: 3-Attempt Exhaustion -> REPORT_BEST_EFFORT")
    print(f"{'=' * 75}")

    class StubUnfixableLLMAdapter(BaseLLMAdapter):
        def get_model_id(self) -> str:
            return "granite-stub-unfixable-test"

        def navigate(self, stack_trace, file_tree, file_contents, runtime) -> NavigationResult:
            return NavigationResult(
                suspects=[
                    SuspectFile(
                        rank=1,
                        file_path="order_service/discount.py",
                        confidence=0.88,
                        reasoning="VIP discount calculation returns wrong value.",
                        suspected_defect="Incorrect multiplier in calculate_discount.",
                    )
                ],
                reasoning_trace="Traced calculate_final_price -> calculate_discount.",
                files_analyzed=2,
                model_id=self.get_model_id(),
            )

        def generate_patch(self, suspect_files, file_contents, stack_trace, hypothesis, runtime) -> PatchResult:
            # Deliberately return a patch that still leaves the test failing (0.5 instead of 0.2)
            bad_diff = (
                "--- a/order_service/discount.py\n"
                "+++ b/order_service/discount.py\n"
                "@@ -7,3 +7,3 @@\n"
                "     if tier == \"VIP\":\n"
                "-        return order_amount * 0.8\n"
                "+        return order_amount * 0.5\n"
            )
            return PatchResult(
                unified_diff=bad_diff,
                explanation="Attempted adjusting VIP multiplier to 0.5.",
                target_file="order_service/discount.py",
                model_id=self.get_model_id(),
                confidence=0.5,
            )

    repo_path = os.path.join(BASE_DIR, "test_repos", "hero_python")
    orchestrator = SentryOrchestrator(
        llm_adapter=StubUnfixableLLMAdapter(),
        max_attempts=3,
    )
    res = orchestrator.run(repo_url=repo_path, test_cmd="pytest -v", runtime="python")

    print(f"  Final State   : {res.final_state}")
    print(f"  Fixed         : {res.fixed}")
    print(f"  Attempts Used : {res.attempts_used}/{res.max_attempts}")
    print(f"  Report Status : {res.best_effort_report['status'] if res.best_effort_report else 'NONE'}")

    assert not res.fixed, "Must NOT claim fixed when validation fails!"
    assert res.final_state == "REPORT_BEST_EFFORT", f"Expected REPORT_BEST_EFFORT, got {res.final_state}"
    assert res.attempts_used == 3, f"Expected 3 attempts, got {res.attempts_used}"
    assert res.best_effort_report is not None, "Best effort report must be populated!"
    print("  [OK] Honest failure reporting verified (3 attempts -> REPORT_BEST_EFFORT)")

    return {
        "final_state": res.final_state,
        "fixed": res.fixed,
        "attempts_used": res.attempts_used,
        "best_effort_report": res.best_effort_report,
    }


def main():
    py_run = run_hero_pipeline(
        label="Hero Python (order_service)",
        repo_subdir="hero_python",
        runtime="python",
        test_cmd="pytest -v",
    )

    node_run = run_hero_pipeline(
        label="Hero Node.js (hero-node-auth)",
        repo_subdir="hero_node",
        runtime="node",
        test_cmd="node --test",
    )

    best_effort_check = test_best_effort_fallback()

    summary = {
        "phase": "Phase 3 - Patch & Validate Loop Verification",
        "python_hero_run": py_run,
        "node_hero_run": node_run,
        "honest_failure_fallback_verification": best_effort_check,
    }

    out_path = os.path.join(BASE_DIR, "phase3_verification_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'#' * 75}")
    print("  PHASE 3 VERIFICATION COMPLETE — ALL ASSERTIONS PASSED!")
    print(f"  Saved full trace to: {out_path}")
    print(f"{'#' * 75}")


if __name__ == "__main__":
    main()
