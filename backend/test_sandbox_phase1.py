"""
Verification Script for Phase 1: Sandbox Execution Layer
Tests both Python and Node.js repositories in an isolated sandbox,
capturing structured execution results and stack traces.
"""

import os
import sys
import json

# Add backend directory to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

from sandbox import get_sandbox, ExecutionResult


def test_python_sandbox():
    print("\n" + "=" * 60)
    print("Testing Sandbox Execution on Python Repository (hero_python)...")
    print("=" * 60)

    repo_path = os.path.join(BASE_DIR, "test_repos", "hero_python")
    sandbox = get_sandbox()
    print(f"Active Sandbox Engine: {sandbox.__class__.__name__}")

    result: ExecutionResult = sandbox.execute(
        repo_url=repo_path,
        commit_sha=None,
        test_cmd="pytest -v",
        runtime="python",
        timeout_seconds=60,
    )

    print(f"Status Passed: {result.passed}")
    print(f"Exit Code: {result.exit_code}")
    print(f"Duration: {result.duration_seconds}s")
    print(f"Sandbox Type: {result.sandbox_type}")
    print("\n--- Extracted Structured Stack Trace ---")
    print(result.stack_trace)
    print("-" * 40)

    assert not result.passed, "Expected Python test to fail (reproducing the hero bug)!"
    assert result.exit_code != 0, "Exit code must be non-zero for test failure!"
    assert "test_vip_customer_discount" in result.stack_trace, "Stack trace must contain the failing test!"
    assert "AssertionError" in result.stack_trace, "Stack trace must contain AssertionError!"

    return result.to_dict()


def test_node_sandbox():
    print("\n" + "=" * 60)
    print("Testing Sandbox Execution on Node.js Repository (hero_node)...")
    print("=" * 60)

    repo_path = os.path.join(BASE_DIR, "test_repos", "hero_node")
    sandbox = get_sandbox()
    print(f"Active Sandbox Engine: {sandbox.__class__.__name__}")

    result: ExecutionResult = sandbox.execute(
        repo_url=repo_path,
        commit_sha=None,
        test_cmd="node --test",
        runtime="node",
        timeout_seconds=60,
    )

    print(f"Status Passed: {result.passed}")
    print(f"Exit Code: {result.exit_code}")
    print(f"Duration: {result.duration_seconds}s")
    print(f"Sandbox Type: {result.sandbox_type}")
    print("\n--- Extracted Structured Stack Trace ---")
    print(result.stack_trace)
    print("-" * 40)

    assert not result.passed, "Expected Node.js test to fail (reproducing the hero bug)!"
    assert result.exit_code != 0, "Exit code must be non-zero for test failure!"
    assert "clock skew" in result.stack_trace or "AssertionError" in result.stack_trace, \
        "Stack trace must contain the failure information!"

    return result.to_dict()


def main():
    py_res = test_python_sandbox()
    node_res = test_node_sandbox()

    output_summary = {
        "phase": "Phase 1 - Sandbox Execution Layer Verification",
        "python_hero_result": py_res,
        "node_hero_result": node_res,
    }

    results_file = os.path.join(BASE_DIR, "phase1_verification_results.json")
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(output_summary, f, indent=2)

    print("\n" + "=" * 60)
    print(f"Phase 1 Verification Succeeded! Results saved to {results_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
