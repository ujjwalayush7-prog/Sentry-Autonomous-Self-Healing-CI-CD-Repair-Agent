"""
Sandbox Execution Layer - Stack Trace Parsers
Extracts human-legible, structured stack traces from Python and Node test runners.
"""

import re
from typing import Optional


def extract_python_stack_trace(stdout: str, stderr: str) -> str:
    """
    Extracts structured stack trace and error message from Python test output (pytest or unittest).
    """
    combined = f"{stdout}\n{stderr}".strip()
    if not combined:
        return ""

    # Check for pytest FAILURES block
    if "=== FAILURES ===" in combined:
        parts = combined.split("=== FAILURES ===")
        if len(parts) > 1:
            failures_section = parts[1]
            # End at the summary line e.g. === short test summary info === or === 1 failed in ...
            end_match = re.search(r"===+ (?:short test summary info|\d+ failed|\d+ error)", failures_section)
            if end_match:
                extracted = failures_section[:end_match.start()].strip()
            else:
                extracted = failures_section.strip()
            if extracted:
                return extracted

    # Check for standard Python Traceback
    tb_matches = list(re.finditer(r"Traceback \(most recent call last\):", combined))
    if tb_matches:
        last_tb = tb_matches[-1]
        tb_text = combined[last_tb.start():]
        # Look for end of exception (usually first empty line or line after Error: message)
        lines = tb_text.splitlines()
        extracted_lines = []
        in_tb = True
        for line in lines:
            extracted_lines.append(line)
            # If line starts without indent and contains Error or Exception after traceback header
            if len(extracted_lines) > 2 and re.match(r"^[A-Za-z0-9_]+(?:Error|Exception):", line):
                break
        return "\n".join(extracted_lines).strip()

    # Fallback: look for lines with FAILED or AssertionError
    failed_lines = [
        line for line in combined.splitlines()
        if any(keyword in line for keyword in ["FAILED", "AssertionError", "Error:", "Exception:"])
    ]
    if failed_lines:
        return "\n".join(failed_lines)

    return stderr.strip() or stdout.strip()[-500:]


def extract_node_stack_trace(stdout: str, stderr: str) -> str:
    """
    Extracts structured stack trace and error message from Node.js test output (node --test, Jest, Mocha).
    """
    combined = f"{stdout}\n{stderr}".strip()
    if not combined:
        return ""

    # 1. Check for node --test failing tests block
    if "failing tests:" in combined:
        parts = combined.split("failing tests:")
        if len(parts) > 1:
            return ("failing tests:" + parts[1]).strip()

    # 2. Check for Jest FAIL block
    if "FAIL " in combined:
        parts = combined.split("FAIL ")
        if len(parts) > 1:
            jest_section = "FAIL " + parts[1]
            end_match = re.search(r"Test Suites:.*", jest_section)
            if end_match:
                extracted = jest_section[:end_match.start()].strip()
            else:
                extracted = jest_section.strip()
            if extracted:
                return extracted

    # 3. Check for standard Node Error / AssertionError stack (Error: ... \n    at ...)
    err_match = re.search(r"((?:[A-Za-z0-9_]+Error|Error|AssertionError)[^\n]*\n(?:\s+at\s+[^\n]+\n?)+)", combined)
    if err_match:
        return err_match.group(1).strip()

    # 4. Check for node --test individual failure marker
    node_test_match = re.search(r"^[✖✖]\s+.+?\n(?:\s+.*?\n)+", combined, re.MULTILINE)
    if node_test_match:
        start_idx = node_test_match.start()
        sub = combined[start_idx:]
        lines = sub.splitlines()
        extracted = []
        for line in lines:
            if extracted and (line.startswith("✔ ") or line.startswith("ℹ tests ") or line.startswith("ℹ pass ")):
                break
            extracted.append(line)
        if extracted:
            return "\n".join(extracted).strip()

    # Fallback to lines with AssertionError or at
    failed_lines = [
        line for line in combined.splitlines()
        if any(keyword in line for keyword in ["AssertionError", "Error:", "  at ", "✖", "FAIL"])
    ]
    if failed_lines:
        return "\n".join(failed_lines)

    return stderr.strip() or stdout.strip()[-500:]


def extract_stack_trace(stdout: str, stderr: str, runtime: str) -> str:
    """Extracts a structured stack trace based on the target runtime."""
    if runtime.lower() in ("python", "py"):
        return extract_python_stack_trace(stdout, stderr)
    elif runtime.lower() in ("node", "nodejs", "javascript", "typescript", "js", "ts"):
        return extract_node_stack_trace(stdout, stderr)
    else:
        # Generic fallback
        return (stderr.strip() or stdout.strip())[-1000:]
