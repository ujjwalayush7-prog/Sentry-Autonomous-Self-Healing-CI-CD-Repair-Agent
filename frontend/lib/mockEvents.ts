/**
 * Mock event sequences for demo playback.
 *
 * PYTHON_MOCK_EVENTS and NODE_MOCK_EVENTS are copied verbatim from
 * phase3_verification_results.json (.python_hero_run.events and
 * .node_hero_run.events respectively).
 *
 * FAILURE_MOCK_EVENTS is synthesised from
 * phase3_verification_results.json .honest_failure_fallback_verification
 * (which has no .events array, only best_effort_report.attempt_history).
 * All event shapes match the canonical schema in backend/orchestrator/events.py.
 */

import { OrchestratorEvent } from "./types";

// ---------------------------------------------------------------------------
// Python hero run — verbatim from python_hero_run.events
// ---------------------------------------------------------------------------
export const PYTHON_MOCK_EVENTS: OrchestratorEvent[] = [
  {
    event_type: "state_transition",
    state: "INGEST",
    timestamp: "2026-09-25T21:08:31+0530",
    message: "Starting Sentry pipeline on test_repos/hero_python (python)",
    data: { from_state: "START", to_state: "INGEST" },
  },
  {
    event_type: "reasoning_step",
    state: "INGEST",
    timestamp: "2026-09-25T21:08:31+0530",
    message: "Cloning repository into isolated working environment...",
    data: {
      step_number: 1,
      description: "Cloning repository into isolated working environment...",
      repo_url: "test_repos/hero_python",
      commit_sha: null,
    },
  },
  {
    event_type: "reasoning_step",
    state: "INGEST",
    timestamp: "2026-09-25T21:08:31+0530",
    message: "Repository ingested and checked out cleanly.",
    data: { step_number: 2, description: "Repository ingested and checked out cleanly." },
  },
  {
    event_type: "state_transition",
    state: "REPRODUCE",
    timestamp: "2026-09-25T21:08:31+0530",
    message: "Executing test command `pytest -v` in sandbox to reproduce failure...",
    data: { from_state: "INGEST", to_state: "REPRODUCE" },
  },
  {
    event_type: "reasoning_step",
    state: "REPRODUCE",
    timestamp: "2026-09-25T21:08:32+0530",
    message: "Initial test run finished: 3/4 passed, 1 failed (exit_code=1).",
    data: {
      step_number: 1,
      description: "Initial test run finished: 3/4 passed, 1 failed (exit_code=1).",
      before_counts: { tests_total: 4, tests_passed: 3, tests_failed: 1 },
      stack_trace:
        "================================\n_________________________ test_vip_customer_discount __________________________\n\n    def test_vip_customer_discount():\n        # VIP customer: 20% discount ($20.0) -> $80 subtotal + 5% tax ($4.0) = $84.0\n        price = calculate_final_price(100.0, \"VIP\", 0.05)\n>       assert price == 84.0, f\"Expected VIP final bill to be 84.0, but received {price}\"\nE       AssertionError: Expected VIP final bill to be 84.0, but received 21.0\nE       assert 21.0 == 84.0\n\ntests/test_pricing.py:20: AssertionError",
      sandbox_type: "local",
    },
  },
  {
    event_type: "state_transition",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:08:32+0530",
    message: "Tracing stack frames and dependency imports to rank suspect root-cause files...",
    data: { from_state: "REPRODUCE", to_state: "NAVIGATE" },
  },
  {
    event_type: "reasoning_step",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:08:32+0530",
    message: "Building repository file tree...",
    data: { step_number: 1, description: "Building repository file tree..." },
  },
  {
    event_type: "reasoning_step",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:08:32+0530",
    message: "File tree built: 8 entries",
    data: {
      step_number: 2,
      description: "File tree built: 8 entries",
      file_tree_preview:
        "hero_python/\n  pyproject.toml\n  order_service/\n    __init__.py\n    discount.py\n    pricing.py\n  tests/\n    test_pricing.py",
    },
  },
  {
    event_type: "reasoning_step",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:08:32+0530",
    message: "Extracted 1 files referenced in stack trace: ['tests/test_pricing.py']",
    data: {
      step_number: 3,
      description: "Extracted 1 files referenced in stack trace: ['tests/test_pricing.py']",
      referenced_files: ["tests/test_pricing.py"],
    },
  },
  {
    event_type: "reasoning_step",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:08:32+0530",
    message:
      "Collected source contents for 2 files (referenced + imports): ['tests/test_pricing.py', 'order_service/pricing.py']",
    data: {
      step_number: 4,
      description:
        "Collected source contents for 2 files (referenced + imports): ['tests/test_pricing.py', 'order_service/pricing.py']",
      files_loaded: ["tests/test_pricing.py", "order_service/pricing.py"],
    },
  },
  {
    event_type: "reasoning_step",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:08:32+0530",
    message: "Calling LLM (gemini-3.5-flash-lite) for root-cause navigation...",
    data: {
      step_number: 5,
      description: "Calling LLM (gemini-3.5-flash-lite) for root-cause navigation...",
      model_id: "gemini-3.5-flash-lite",
    },
  },
  {
    event_type: "suspect_ranking",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:08:35+0530",
    message: "Navigation complete: 2 suspect files ranked using gemini-3.5-flash-lite",
    data: {
      suspects: [
        {
          rank: 1,
          file_path: "order_service/discount.py",
          confidence: 0.95,
          reasoning:
            "The pricing calculation delegates discount computation to calculate_discount in discount.py. Since the test expected a VIP discount of 20.0 but received a completely different calculation yielding 21.0, the defect likely lies within the discount logic itself.",
          suspected_defect:
            "Incorrect discount rate or calculation for the VIP tier in the discount module.",
          relevant_lines: null,
        },
        {
          rank: 2,
          file_path: "order_service/pricing.py",
          confidence: 0.05,
          reasoning:
            "pricing.py calls calculate_discount and correctly subtracts it before applying tax. While it orchestrates the math, the error in the final value is primarily driven by the underlying discount logic.",
          suspected_defect: "Possible incorrect handling of order amounts during pricing combination.",
          relevant_lines: "10-14",
        },
      ],
      reasoning_trace:
        "The test failure indicates that an order of 100.0 for a VIP customer yielded a final price of 21.0 instead of the expected 84.0. Tracing backward, calculate_final_price in pricing.py calls calculate_discount from order_service/discount.py. Since pricing.py correctly subtracts the discount and applies tax, the incorrect discount value originates in order_service/discount.py.",
      files_analyzed: 2,
      model_id: "gemini-3.5-flash-lite",
    },
  },
  {
    event_type: "reasoning_step",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:08:35+0530",
    message: "Navigation complete. Top suspect: order_service/discount.py (confidence: 0.95)",
    data: {
      step_number: 6,
      description: "Navigation complete. Top suspect: order_service/discount.py (confidence: 0.95)",
      top_suspect: {
        rank: 1,
        file_path: "order_service/discount.py",
        confidence: 0.95,
        reasoning:
          "The pricing calculation delegates discount computation to calculate_discount in discount.py.",
        suspected_defect:
          "Incorrect discount rate or calculation for the VIP tier in the discount module.",
        relevant_lines: null,
      },
    },
  },
  {
    event_type: "state_transition",
    state: "HYPOTHESIZE",
    timestamp: "2026-09-25T21:08:35+0530",
    message: "Formulating root-cause hypothesis from top suspect files...",
    data: { from_state: "NAVIGATE", to_state: "HYPOTHESIZE" },
  },
  {
    event_type: "reasoning_step",
    state: "HYPOTHESIZE",
    timestamp: "2026-09-25T21:08:35+0530",
    message:
      "Hypothesis formulated: Primary Suspect: order_service/discount.py (confidence 0.95). Suspected Defect: Incorrect discount rate or calculation for the VIP tier.",
    data: {
      step_number: 1,
      description:
        "Hypothesis formulated: Primary Suspect: order_service/discount.py (confidence 0.95). Suspected Defect: Incorrect discount rate or calculation for the VIP tier.",
      hypothesis:
        "Primary Suspect: order_service/discount.py (confidence 0.95). Reasoning: The pricing calculation delegates discount computation to calculate_discount in discount.py. Suspected Defect: Incorrect discount rate or calculation for the VIP tier.",
      files_loaded_for_patch: [
        "order_service/discount.py",
        "order_service/pricing.py",
        "order_service/__init__.py",
        "tests/test_pricing.py",
      ],
    },
  },
  {
    event_type: "state_transition",
    state: "PATCH",
    timestamp: "2026-09-25T21:08:35+0530",
    message: "Generating minimal surgical patch (Attempt 1 of 3)...",
    data: { from_state: "HYPOTHESIZE", to_state: "PATCH" },
  },
  {
    event_type: "patch_generated",
    state: "PATCH",
    timestamp: "2026-09-25T21:08:37+0530",
    message: "Patch generated for order_service/discount.py (attempt 1)",
    data: {
      target_file: "order_service/discount.py",
      unified_diff:
        "diff --git a/order_service/discount.py b/order_service/discount.py\nindex 15d56e8..9e3db53 100644\n--- a/order_service/discount.py\n+++ b/order_service/discount.py\n@@ -5,8 +5,7 @@ def calculate_discount(order_amount: float, tier: str) -> float:\n     GOLD tier receives a 10% discount (0.10 * order_amount).\n     \"\"\"\n     if tier == \"VIP\":\n-        # BUG: Erroneously returns net price factor rather than deduction amount\n-        return order_amount * 0.8\n+        return order_amount * 0.2\n     elif tier == \"GOLD\":\n         return order_amount * 0.1\n     return 0.0",
      explanation:
        "The calculate_discount function for the VIP tier was incorrectly returning the remaining price factor (order_amount * 0.8) instead of the actual discount deduction amount (order_amount * 0.2). Changing the multiplier to 0.2 correctly computes the 20% discount deduction.",
      attempt: 1,
      model_id: "gemini-3.5-flash-lite",
    },
  },
  {
    event_type: "reasoning_step",
    state: "PATCH",
    timestamp: "2026-09-25T21:08:37+0530",
    message:
      "Patch application status: Successfully applied patch to order_service/discount.py (direct hunk engine)",
    data: {
      step_number: 1,
      description:
        "Patch application status: Successfully applied patch to order_service/discount.py (direct hunk engine)",
      applied: true,
      explanation:
        "The calculate_discount function for the VIP tier was incorrectly returning the remaining price factor.",
    },
  },
  {
    event_type: "state_transition",
    state: "VALIDATE",
    timestamp: "2026-09-25T21:08:37+0530",
    message: "Validating patched codebase against full test suite (Attempt 1)...",
    data: { from_state: "PATCH", to_state: "VALIDATE" },
  },
  {
    event_type: "validation_result",
    state: "VALIDATE",
    timestamp: "2026-09-25T21:08:37+0530",
    message: "Validation PASSED: 4/4 tests passed (attempt 1)",
    data: {
      passed: true,
      tests_passed: 4,
      tests_failed: 0,
      tests_total: 4,
      attempt: 1,
      stdout_summary:
        "collected 4 items\n\ntests/test_pricing.py::test_regular_customer_no_discount PASSED [ 25%]\ntests/test_pricing.py::test_gold_customer_discount PASSED      [ 50%]\ntests/test_pricing.py::test_vip_customer_discount PASSED       [ 75%]\ntests/test_pricing.py::test_zero_amount_order PASSED           [100%]\n\n============================== 4 passed in 0.06s ==============================",
    },
  },
  {
    event_type: "reasoning_step",
    state: "VALIDATE",
    timestamp: "2026-09-25T21:08:37+0530",
    message: "RED -> GREEN achieved on attempt 1! Before: 3/4 passed. After: 4/4 passed.",
    data: {
      step_number: 1,
      description: "RED -> GREEN achieved on attempt 1! Before: 3/4 passed. After: 4/4 passed.",
      before_counts: { tests_total: 4, tests_passed: 3, tests_failed: 1 },
      after_counts: { tests_total: 4, tests_passed: 4, tests_failed: 0 },
    },
  },
  {
    event_type: "state_transition",
    state: "PR_CREATE",
    timestamp: "2026-09-25T21:08:37+0530",
    message: "All tests green! Ready for Pull Request creation.",
    data: { from_state: "VALIDATE", to_state: "PR_CREATE" },
  },
];

// ---------------------------------------------------------------------------
// Node.js hero run — verbatim from node_hero_run.events
// ---------------------------------------------------------------------------
export const NODE_MOCK_EVENTS: OrchestratorEvent[] = [
  {
    event_type: "state_transition",
    state: "INGEST",
    timestamp: "2026-09-25T21:08:38+0530",
    message: "Starting Sentry pipeline on test_repos/hero_node (node)",
    data: { from_state: "START", to_state: "INGEST" },
  },
  {
    event_type: "reasoning_step",
    state: "INGEST",
    timestamp: "2026-09-25T21:08:38+0530",
    message: "Cloning repository into isolated working environment...",
    data: {
      step_number: 1,
      description: "Cloning repository into isolated working environment...",
      repo_url: "test_repos/hero_node",
      commit_sha: null,
    },
  },
  {
    event_type: "reasoning_step",
    state: "INGEST",
    timestamp: "2026-09-25T21:08:38+0530",
    message: "Repository ingested and checked out cleanly.",
    data: { step_number: 2, description: "Repository ingested and checked out cleanly." },
  },
  {
    event_type: "state_transition",
    state: "REPRODUCE",
    timestamp: "2026-09-25T21:08:38+0530",
    message: "Executing test command `node --test` in sandbox to reproduce failure...",
    data: { from_state: "INGEST", to_state: "REPRODUCE" },
  },
  {
    event_type: "reasoning_step",
    state: "REPRODUCE",
    timestamp: "2026-09-25T21:08:40+0530",
    message: "Initial test run finished: 2/3 passed, 1 failed (exit_code=1).",
    data: {
      step_number: 1,
      description: "Initial test run finished: 2/3 passed, 1 failed (exit_code=1).",
      before_counts: { tests_total: 3, tests_passed: 2, tests_failed: 1 },
      stack_trace:
        "failing tests:\n\ntest at test/session.test.js:16:3\n✖ should tolerate clock skew when token is near expiration boundary (0.794ms)\n  AssertionError [ERR_ASSERTION]: Token within clock skew tolerance should be considered valid\n  false !== true",
      sandbox_type: "local",
    },
  },
  {
    event_type: "state_transition",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:08:40+0530",
    message: "Tracing stack frames and dependency imports to rank suspect root-cause files...",
    data: { from_state: "REPRODUCE", to_state: "NAVIGATE" },
  },
  {
    event_type: "reasoning_step",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:08:40+0530",
    message: "Building repository file tree...",
    data: { step_number: 1, description: "Building repository file tree..." },
  },
  {
    event_type: "reasoning_step",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:08:40+0530",
    message: "File tree built: 7 entries",
    data: {
      step_number: 2,
      description: "File tree built: 7 entries",
      file_tree_preview:
        "hero_node/\n  package.json\n  src/\n    session_manager.js\n    token_validator.js\n  test/\n    session.test.js",
    },
  },
  {
    event_type: "reasoning_step",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:08:40+0530",
    message: "Extracted 1 files referenced in stack trace: ['test/session.test.js']",
    data: {
      step_number: 3,
      description: "Extracted 1 files referenced in stack trace: ['test/session.test.js']",
      referenced_files: ["test/session.test.js"],
    },
  },
  {
    event_type: "reasoning_step",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:08:40+0530",
    message:
      "Collected source contents for 2 files (referenced + imports): ['test/session.test.js', 'src/session_manager.js']",
    data: {
      step_number: 4,
      description:
        "Collected source contents for 2 files (referenced + imports): ['test/session.test.js', 'src/session_manager.js']",
      files_loaded: ["test/session.test.js", "src/session_manager.js"],
    },
  },
  {
    event_type: "reasoning_step",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:08:40+0530",
    message: "Calling LLM (gemini-3.5-flash-lite) for root-cause navigation...",
    data: {
      step_number: 5,
      description: "Calling LLM (gemini-3.5-flash-lite) for root-cause navigation...",
      model_id: "gemini-3.5-flash-lite",
    },
  },
  {
    event_type: "suspect_ranking",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:08:42+0530",
    message: "Navigation complete: 2 suspect files ranked using gemini-3.5-flash-lite",
    data: {
      suspects: [
        {
          rank: 1,
          file_path: "src/token_validator.js",
          confidence: 0.95,
          reasoning:
            "The test failed because a token past its nominal expiration but within the clock skew allowance was marked as expired. Since session_manager.js delegates expiration logic to isTokenExpired in token_validator.js, the incorrect clock skew comparison or math must reside there.",
          suspected_defect:
            "The token validator likely incorrectly subtracts or applies the clock skew tolerance instead of adding it.",
          relevant_lines: null,
        },
        {
          rank: 2,
          file_path: "src/session_manager.js",
          confidence: 0.05,
          reasoning:
            "Passes the clock skew parameter correctly to the token validator, but could potentially be passing arguments in the wrong order.",
          suspected_defect: "Argument order mismatch when calling isTokenExpired.",
          relevant_lines: "7-12",
        },
      ],
      reasoning_trace:
        "The failing test asserts that a session at timestamp 1315 should be valid despite token expiration at 1300, because it falls within a 30-second clock skew tolerance (up to 1330). The root cause must be inside token_validator.js where the clock skew arithmetic and comparison logic are implemented.",
      files_analyzed: 2,
      model_id: "gemini-3.5-flash-lite",
    },
  },
  {
    event_type: "reasoning_step",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:08:42+0530",
    message: "Navigation complete. Top suspect: src/token_validator.js (confidence: 0.95)",
    data: {
      step_number: 6,
      description: "Navigation complete. Top suspect: src/token_validator.js (confidence: 0.95)",
      top_suspect: {
        rank: 1,
        file_path: "src/token_validator.js",
        confidence: 0.95,
        reasoning:
          "The test failed because a token past its nominal expiration but within the clock skew allowance was marked as expired.",
        suspected_defect: "The token validator likely incorrectly subtracts the clock skew tolerance instead of adding it.",
        relevant_lines: null,
      },
    },
  },
  {
    event_type: "state_transition",
    state: "HYPOTHESIZE",
    timestamp: "2026-09-25T21:08:42+0530",
    message: "Formulating root-cause hypothesis from top suspect files...",
    data: { from_state: "NAVIGATE", to_state: "HYPOTHESIZE" },
  },
  {
    event_type: "reasoning_step",
    state: "HYPOTHESIZE",
    timestamp: "2026-09-25T21:08:42+0530",
    message:
      "Hypothesis formulated: Primary Suspect: src/token_validator.js (confidence 0.95). Suspected Defect: Clock skew subtraction instead of addition.",
    data: {
      step_number: 1,
      description:
        "Hypothesis formulated: Primary Suspect: src/token_validator.js (confidence 0.95). Suspected Defect: Clock skew subtraction instead of addition.",
      hypothesis:
        "Primary Suspect: src/token_validator.js (confidence 0.95). The token validator incorrectly subtracts the clock skew tolerance instead of adding it.",
      files_loaded_for_patch: [
        "src/token_validator.js",
        "src/session_manager.js",
        "test/session.test.js",
      ],
    },
  },
  {
    event_type: "state_transition",
    state: "PATCH",
    timestamp: "2026-09-25T21:08:42+0530",
    message: "Generating minimal surgical patch (Attempt 1 of 3)...",
    data: { from_state: "HYPOTHESIZE", to_state: "PATCH" },
  },
  {
    event_type: "patch_generated",
    state: "PATCH",
    timestamp: "2026-09-25T21:08:44+0530",
    message: "Patch generated for src/token_validator.js (attempt 1)",
    data: {
      target_file: "src/token_validator.js",
      unified_diff:
        "diff --git a/src/token_validator.js b/src/token_validator.js\nindex 838465d..7530cb8 100644\n--- a/src/token_validator.js\n+++ b/src/token_validator.js\n@@ -10,7 +10,7 @@ function isTokenExpired(issuedAtEpochSec, ttlSec, currentEpochSec, clockSkewAllo\n   const expiresAt = issuedAtEpochSec + ttlSec;\n   // BUG: Premature expiration: Subtracts clockSkewAllowanceSec instead of adding it,\n   // making the valid window smaller rather than granting tolerance for clock drift.\n-  return currentEpochSec > (expiresAt - clockSkewAllowanceSec);\n+  return currentEpochSec > (expiresAt + clockSkewAllowanceSec);\n }\n \n module.exports = { isTokenExpired };",
      explanation:
        "The token validator was incorrectly subtracting the clock skew allowance instead of adding it when calculating the expiration threshold. By changing the subtraction to an addition, the valid time window correctly accounts for clock drift tolerance.",
      attempt: 1,
      model_id: "gemini-3.5-flash-lite",
    },
  },
  {
    event_type: "reasoning_step",
    state: "PATCH",
    timestamp: "2026-09-25T21:08:44+0530",
    message:
      "Patch application status: Successfully applied patch to src/token_validator.js (direct hunk engine)",
    data: {
      step_number: 1,
      description:
        "Patch application status: Successfully applied patch to src/token_validator.js (direct hunk engine)",
      applied: true,
      explanation:
        "The token validator was incorrectly subtracting the clock skew allowance instead of adding it.",
    },
  },
  {
    event_type: "state_transition",
    state: "VALIDATE",
    timestamp: "2026-09-25T21:08:44+0530",
    message: "Validating patched codebase against full test suite (Attempt 1)...",
    data: { from_state: "PATCH", to_state: "VALIDATE" },
  },
  {
    event_type: "validation_result",
    state: "VALIDATE",
    timestamp: "2026-09-25T21:08:44+0530",
    message: "Validation PASSED: 3/3 tests passed (attempt 1)",
    data: {
      passed: true,
      tests_passed: 3,
      tests_failed: 0,
      tests_total: 3,
      attempt: 1,
      stdout_summary:
        "▶ Session Manager Verification\n  ✔ should validate active fresh session (0.6119ms)\n  ✔ should tolerate clock skew when token is near expiration boundary (0.1134ms)\n  ✔ should reject genuinely expired token beyond clock skew (0.0967ms)\n✔ Session Manager Verification (1.6408ms)\n\ntests 3  pass 3  fail 0",
    },
  },
  {
    event_type: "reasoning_step",
    state: "VALIDATE",
    timestamp: "2026-09-25T21:08:44+0530",
    message: "RED -> GREEN achieved on attempt 1! Before: 2/3 passed. After: 3/3 passed.",
    data: {
      step_number: 1,
      description: "RED -> GREEN achieved on attempt 1! Before: 2/3 passed. After: 3/3 passed.",
      before_counts: { tests_total: 3, tests_passed: 2, tests_failed: 1 },
      after_counts: { tests_total: 3, tests_passed: 3, tests_failed: 0 },
    },
  },
  {
    event_type: "state_transition",
    state: "PR_CREATE",
    timestamp: "2026-09-25T21:08:44+0530",
    message: "All tests green! Ready for Pull Request creation.",
    data: { from_state: "VALIDATE", to_state: "PR_CREATE" },
  },
];

// ---------------------------------------------------------------------------
// Failure scenario — synthesised from honest_failure_fallback_verification.
// The source JSON has no .events array; events are constructed from
// best_effort_report.attempt_history using canonical event shapes.
// ---------------------------------------------------------------------------
const FAILURE_STACK_TRACE =
  "================================\n_________________________ test_vip_customer_discount __________________________\n\n    def test_vip_customer_discount():\n        price = calculate_final_price(100.0, \"VIP\", 0.05)\n>       assert price == 84.0, f\"Expected VIP final bill to be 84.0, but received {price}\"\nE       AssertionError: Expected VIP final bill to be 84.0, but received 52.5\nE       assert 52.5 == 84.0\n\ntests/test_pricing.py:20: AssertionError";

const FAILURE_DIFF =
  "diff --git a/order_service/discount.py b/order_service/discount.py\nindex 15d56e8..075b8d2 100644\n--- a/order_service/discount.py\n+++ b/order_service/discount.py\n@@ -6,7 +6,7 @@ def calculate_discount(order_amount: float, tier: str) -> float:\n     \"\"\"\n     if tier == \"VIP\":\n         # BUG: Erroneously returns net price factor rather than deduction amount\n-        return order_amount * 0.8\n+        return order_amount * 0.5\n     elif tier == \"GOLD\":\n         return order_amount * 0.1\n     return 0.0";

export const FAILURE_MOCK_EVENTS: OrchestratorEvent[] = [
  // --- INGEST ---
  {
    event_type: "state_transition",
    state: "INGEST",
    timestamp: "2026-09-25T21:09:00+0530",
    message: "Starting Sentry pipeline on test_repos/hero_python (python)",
    data: { from_state: "START", to_state: "INGEST" },
  },
  {
    event_type: "reasoning_step",
    state: "INGEST",
    timestamp: "2026-09-25T21:09:00+0530",
    message: "Cloning repository into isolated working environment...",
    data: {
      step_number: 1,
      description: "Cloning repository into isolated working environment...",
      repo_url: "test_repos/hero_python",
      commit_sha: null,
    },
  },
  {
    event_type: "reasoning_step",
    state: "INGEST",
    timestamp: "2026-09-25T21:09:00+0530",
    message: "Repository ingested and checked out cleanly.",
    data: { step_number: 2, description: "Repository ingested and checked out cleanly." },
  },
  // --- REPRODUCE ---
  {
    event_type: "state_transition",
    state: "REPRODUCE",
    timestamp: "2026-09-25T21:09:00+0530",
    message: "Executing test command `pytest -v` in sandbox to reproduce failure...",
    data: { from_state: "INGEST", to_state: "REPRODUCE" },
  },
  {
    event_type: "reasoning_step",
    state: "REPRODUCE",
    timestamp: "2026-09-25T21:09:01+0530",
    message: "Initial test run finished: 3/4 passed, 1 failed (exit_code=1).",
    data: {
      step_number: 1,
      description: "Initial test run finished: 3/4 passed, 1 failed (exit_code=1).",
      before_counts: { tests_total: 4, tests_passed: 3, tests_failed: 1 },
      stack_trace: FAILURE_STACK_TRACE,
      sandbox_type: "local",
    },
  },
  // --- NAVIGATE ---
  {
    event_type: "state_transition",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:09:01+0530",
    message: "Tracing stack frames and dependency imports to rank suspect root-cause files...",
    data: { from_state: "REPRODUCE", to_state: "NAVIGATE" },
  },
  {
    event_type: "reasoning_step",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:09:01+0530",
    message: "Building repository file tree...",
    data: { step_number: 1, description: "Building repository file tree..." },
  },
  {
    event_type: "reasoning_step",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:09:01+0530",
    message: "Calling LLM (granite-stub-unfixable-test) for root-cause navigation...",
    data: {
      step_number: 2,
      description: "Calling LLM (granite-stub-unfixable-test) for root-cause navigation...",
      model_id: "granite-stub-unfixable-test",
    },
  },
  {
    event_type: "suspect_ranking",
    state: "NAVIGATE",
    timestamp: "2026-09-25T21:09:01+0530",
    message: "Navigation complete: 1 suspect files ranked using granite-stub-unfixable-test",
    data: {
      suspects: [
        {
          rank: 1,
          file_path: "order_service/discount.py",
          confidence: 0.88,
          reasoning: "VIP discount calculation returns wrong value.",
          suspected_defect: "Incorrect multiplier in calculate_discount.",
          relevant_lines: null,
        },
      ],
      reasoning_trace: "Traced calculate_final_price -> calculate_discount.",
      files_analyzed: 2,
      model_id: "granite-stub-unfixable-test",
    },
  },
  // --- HYPOTHESIZE ---
  {
    event_type: "state_transition",
    state: "HYPOTHESIZE",
    timestamp: "2026-09-25T21:09:01+0530",
    message: "Formulating root-cause hypothesis from top suspect files...",
    data: { from_state: "NAVIGATE", to_state: "HYPOTHESIZE" },
  },
  {
    event_type: "reasoning_step",
    state: "HYPOTHESIZE",
    timestamp: "2026-09-25T21:09:01+0530",
    message:
      "Hypothesis formulated: Primary Suspect: order_service/discount.py (confidence 0.88). Suspected Defect: Incorrect multiplier in calculate_discount.",
    data: {
      step_number: 1,
      description:
        "Hypothesis formulated: Primary Suspect: order_service/discount.py (confidence 0.88). Suspected Defect: Incorrect multiplier in calculate_discount.",
      hypothesis:
        "Primary Suspect: order_service/discount.py (confidence 0.88). Suspected Defect: Incorrect multiplier in calculate_discount.",
      files_loaded_for_patch: ["order_service/discount.py", "tests/test_pricing.py"],
    },
  },
  // --- Attempt 1: PATCH -> VALIDATE (fail) ---
  {
    event_type: "state_transition",
    state: "PATCH",
    timestamp: "2026-09-25T21:09:01+0530",
    message: "Generating minimal surgical patch (Attempt 1 of 3)...",
    data: { from_state: "HYPOTHESIZE", to_state: "PATCH" },
  },
  {
    event_type: "patch_generated",
    state: "PATCH",
    timestamp: "2026-09-25T21:09:02+0530",
    message: "Patch generated for order_service/discount.py (attempt 1)",
    data: {
      target_file: "order_service/discount.py",
      unified_diff: FAILURE_DIFF,
      explanation: "Attempted adjusting VIP multiplier to 0.5.",
      attempt: 1,
      model_id: "granite-stub-unfixable-test",
    },
  },
  {
    event_type: "state_transition",
    state: "VALIDATE",
    timestamp: "2026-09-25T21:09:02+0530",
    message: "Validating patched codebase against full test suite (Attempt 1)...",
    data: { from_state: "PATCH", to_state: "VALIDATE" },
  },
  {
    event_type: "validation_result",
    state: "VALIDATE",
    timestamp: "2026-09-25T21:09:02+0530",
    message: "Validation FAILED: 3/4 tests passed (attempt 1)",
    data: {
      passed: false,
      tests_passed: 3,
      tests_failed: 1,
      tests_total: 4,
      attempt: 1,
      stdout_summary: "FAILED tests/test_pricing.py::test_vip_customer_discount - AssertionError: Expected VIP final bill to be 84.0, but received 52.5",
    },
  },
  // --- Attempt 2: PATCH -> VALIDATE (fail) ---
  {
    event_type: "state_transition",
    state: "PATCH",
    timestamp: "2026-09-25T21:09:02+0530",
    message: "Validation failed. Reverting patch and retrying (Attempt 2 of 3)...",
    data: { from_state: "VALIDATE", to_state: "PATCH" },
  },
  {
    event_type: "patch_generated",
    state: "PATCH",
    timestamp: "2026-09-25T21:09:03+0530",
    message: "Patch generated for order_service/discount.py (attempt 2)",
    data: {
      target_file: "order_service/discount.py",
      unified_diff: FAILURE_DIFF,
      explanation: "Attempted adjusting VIP multiplier to 0.5.",
      attempt: 2,
      model_id: "granite-stub-unfixable-test",
    },
  },
  {
    event_type: "state_transition",
    state: "VALIDATE",
    timestamp: "2026-09-25T21:09:03+0530",
    message: "Validating patched codebase against full test suite (Attempt 2)...",
    data: { from_state: "PATCH", to_state: "VALIDATE" },
  },
  {
    event_type: "validation_result",
    state: "VALIDATE",
    timestamp: "2026-09-25T21:09:03+0530",
    message: "Validation FAILED: 3/4 tests passed (attempt 2)",
    data: {
      passed: false,
      tests_passed: 3,
      tests_failed: 1,
      tests_total: 4,
      attempt: 2,
      stdout_summary: "FAILED tests/test_pricing.py::test_vip_customer_discount - AssertionError: Expected VIP final bill to be 84.0, but received 52.5",
    },
  },
  // --- Attempt 3: PATCH -> VALIDATE (fail) ---
  {
    event_type: "state_transition",
    state: "PATCH",
    timestamp: "2026-09-25T21:09:03+0530",
    message: "Validation failed. Reverting patch and retrying (Attempt 3 of 3)...",
    data: { from_state: "VALIDATE", to_state: "PATCH" },
  },
  {
    event_type: "patch_generated",
    state: "PATCH",
    timestamp: "2026-09-25T21:09:04+0530",
    message: "Patch generated for order_service/discount.py (attempt 3)",
    data: {
      target_file: "order_service/discount.py",
      unified_diff: FAILURE_DIFF,
      explanation: "Attempted adjusting VIP multiplier to 0.5.",
      attempt: 3,
      model_id: "granite-stub-unfixable-test",
    },
  },
  {
    event_type: "state_transition",
    state: "VALIDATE",
    timestamp: "2026-09-25T21:09:04+0530",
    message: "Validating patched codebase against full test suite (Attempt 3)...",
    data: { from_state: "PATCH", to_state: "VALIDATE" },
  },
  {
    event_type: "validation_result",
    state: "VALIDATE",
    timestamp: "2026-09-25T21:09:04+0530",
    message: "Validation FAILED: 3/4 tests passed (attempt 3)",
    data: {
      passed: false,
      tests_passed: 3,
      tests_failed: 1,
      tests_total: 4,
      attempt: 3,
      stdout_summary: "FAILED tests/test_pricing.py::test_vip_customer_discount - AssertionError: Expected VIP final bill to be 84.0, but received 52.5",
    },
  },
  // --- REPORT_BEST_EFFORT (terminal) ---
  {
    event_type: "state_transition",
    state: "REPORT_BEST_EFFORT",
    timestamp: "2026-09-25T21:09:04+0530",
    message: "Maximum attempts (3) exhausted without achieving GREEN. Emitting diagnostic report.",
    data: { from_state: "VALIDATE", to_state: "REPORT_BEST_EFFORT" },
  },
  {
    event_type: "best_effort_report",
    state: "REPORT_BEST_EFFORT",
    timestamp: "2026-09-25T21:09:04+0530",
    message:
      "Best-effort diagnostic report: UNRESOLVED_AFTER_MAX_ATTEMPTS. 3 attempts exhausted.",
    data: {
      status: "UNRESOLVED_AFTER_MAX_ATTEMPTS",
      attempts_exhausted: 3,
      best_hypothesis:
        "Primary Suspect: order_service/discount.py (confidence 0.88). Reasoning: VIP discount calculation returns wrong value. Suspected Defect: Incorrect multiplier in calculate_discount.",
      top_suspects: [
        {
          rank: 1,
          file_path: "order_service/discount.py",
          confidence: 0.88,
          reasoning: "VIP discount calculation returns wrong value.",
          suspected_defect: "Incorrect multiplier in calculate_discount.",
          relevant_lines: null,
        },
      ],
      attempt_history: [1, 2, 3].map((n) => ({
        attempt: n,
        target_file: "order_service/discount.py",
        unified_diff: FAILURE_DIFF,
        explanation: "Attempted adjusting VIP multiplier to 0.5.",
        patch_applied: true,
        validation_passed: false,
        tests_total: 4,
        tests_passed: 3,
        tests_failed: 1,
        stack_trace: FAILURE_STACK_TRACE,
      })),
    },
  },
];

// ---------------------------------------------------------------------------
// Scenario registry
// ---------------------------------------------------------------------------
export const MOCK_SCENARIOS = {
  python: PYTHON_MOCK_EVENTS,
  node: NODE_MOCK_EVENTS,
  failure: FAILURE_MOCK_EVENTS,
} as const;

export type MockScenarioKey = keyof typeof MOCK_SCENARIOS;
