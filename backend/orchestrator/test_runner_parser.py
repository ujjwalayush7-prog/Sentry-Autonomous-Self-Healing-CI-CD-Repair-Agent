"""
Test Runner Output Count Parser
Extracts structured test counts (total, passed, failed) from Python (pytest)
and Node.js (node --test, Jest, Mocha) outputs.
"""

import re
from typing import Dict


def parse_test_counts(stdout: str, stderr: str, passed: bool, runtime: str) -> Dict[str, int]:
    """
    Parses total, passed, and failed test counts from test runner output.

    Returns:
        {"tests_total": int, "tests_passed": int, "tests_failed": int}
    """
    combined = f"{stdout}\n{stderr}"

    if runtime.lower() in ("python", "py"):
        return _parse_python_counts(combined, passed)
    elif runtime.lower() in ("node", "nodejs", "js", "ts", "javascript", "typescript"):
        return _parse_node_counts(combined, passed)
    else:
        return {"tests_total": 1, "tests_passed": 1 if passed else 0, "tests_failed": 0 if passed else 1}


def _parse_python_counts(text: str, passed: bool) -> Dict[str, int]:
    # Look for pytest summary line: e.g. "=== 1 failed, 3 passed in 0.12s ===" or "=== 4 passed in 0.05s ==="
    failed_match = re.search(r"(\d+)\s+failed", text)
    passed_match = re.search(r"(\d+)\s+passed", text)
    error_match = re.search(r"(\d+)\s+errors?", text)

    n_failed = int(failed_match.group(1)) if failed_match else 0
    if error_match:
        n_failed += int(error_match.group(1))
    n_passed = int(passed_match.group(1)) if passed_match else 0

    total = n_passed + n_failed
    if total == 0:
        # Try "collected X items"
        col_match = re.search(r"collected\s+(\d+)\s+items?", text)
        if col_match:
            total = int(col_match.group(1))
            n_passed = total if passed else max(0, total - 1)
            n_failed = 0 if passed else 1
        else:
            total = 1
            n_passed = 1 if passed else 0
            n_failed = 0 if passed else 1

    return {
        "tests_total": total,
        "tests_passed": n_passed,
        "tests_failed": n_failed,
    }


def _parse_node_counts(text: str, passed: bool) -> Dict[str, int]:
    # 1. Check node --test summary:
    # ℹ tests 3
    # ℹ pass 2
    # ℹ fail 1
    tests_match = re.search(r"tests\s+(\d+)", text)
    pass_match = re.search(r"pass\s+(\d+)", text)
    fail_match = re.search(r"fail\s+(\d+)", text)

    if tests_match and pass_match:
        total = int(tests_match.group(1))
        n_passed = int(pass_match.group(1))
        n_failed = int(fail_match.group(1)) if fail_match else (total - n_passed)
        return {
            "tests_total": total,
            "tests_passed": n_passed,
            "tests_failed": n_failed,
        }

    # 2. Check Jest summary: "Tests: 1 failed, 2 passed, 3 total"
    jest_fail = re.search(r"Tests:.*?(\d+)\s+failed", text)
    jest_pass = re.search(r"Tests:.*?(\d+)\s+passed", text)
    jest_total = re.search(r"Tests:.*?(\d+)\s+total", text)
    if jest_total:
        total = int(jest_total.group(1))
        n_passed = int(jest_pass.group(1)) if jest_pass else 0
        n_failed = int(jest_fail.group(1)) if jest_fail else (total - n_passed)
        return {
            "tests_total": total,
            "tests_passed": n_passed,
            "tests_failed": n_failed,
        }

    # Fallback: count checkmarks and crosses
    n_passed = len(re.findall(r"✔", text))
    n_failed = len(re.findall(r"✖", text))
    if n_passed + n_failed > 0:
        return {
            "tests_total": n_passed + n_failed,
            "tests_passed": n_passed,
            "tests_failed": n_failed,
        }

    return {
        "tests_total": 1,
        "tests_passed": 1 if passed else 0,
        "tests_failed": 0 if passed else 1,
    }
