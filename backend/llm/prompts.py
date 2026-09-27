"""
Navigation and Patch Generation Prompt Templates
Carefully engineered to maximize root-cause accuracy from stack traces.
"""

NAVIGATION_SYSTEM_PROMPT = """\
You are an expert software debugging agent. Your task is to analyze a failing test's stack trace, \
the repository file tree, and relevant source file contents to identify the ROOT CAUSE file — \
NOT the file where the test assertion fires, but the file containing the actual defect that \
causes the wrong behavior.

Key principles:
1. Stack traces show WHERE the failure is observed, not necessarily WHERE the bug lives.
2. Follow the data flow BACKWARD from the assertion. If a function returns the wrong value, \
   the bug is likely in that function's implementation or in a function IT calls.
3. Cross-file defects are common: a test file calls function A in file X, which calls function B \
   in file Y. The defect may be in file Y even though file X appears in the stack trace.
4. Look for semantic errors: wrong operators (+/-), wrong constants, inverted conditions, \
   off-by-one errors, wrong variable references.
5. Rank files by likelihood of containing the ROOT CAUSE, not by proximity to the test assertion.

You MUST respond with ONLY a valid JSON object (no markdown fences, no commentary outside the JSON)."""


def build_navigation_prompt(
    stack_trace: str,
    file_tree: str,
    file_contents: dict,
    runtime: str,
) -> str:
    """Builds the navigation user prompt."""

    files_section = ""
    for path, content in file_contents.items():
        files_section += f"\n--- FILE: {path} ---\n{content}\n--- END FILE ---\n"

    return f"""\
RUNTIME: {runtime}

FAILING TEST STACK TRACE:
```
{stack_trace}
```

REPOSITORY FILE TREE:
```
{file_tree}
```

RELEVANT SOURCE FILES:
{files_section}

TASK: Analyze the stack trace and source files. Identify which file contains the ROOT CAUSE \
defect — the actual bug that produces the wrong behavior, NOT the test file that observes the failure.

Follow the data flow backward from the assertion to find where the incorrect value originates.

Respond with this exact JSON structure (include at least 2 ranked suspect source files):
{{
  "suspects": [
    {{
      "rank": 1,
      "file_path": "<most likely root-cause source file path relative to repo root>",
      "confidence": <float 0.0-1.0>,
      "reasoning": "<2-3 sentences explaining WHY this file likely contains the root cause>",
      "suspected_defect": "<specific description of what the bug probably is>",
      "relevant_lines": "<line range or null>"
    }},
    {{
      "rank": 2,
      "file_path": "<second suspect source file path relative to repo root>",
      "confidence": <float 0.0-1.0>,
      "reasoning": "<2-3 sentences explaining why this file is less likely than rank 1>",
      "suspected_defect": "<potential secondary defect or caller interaction>",
      "relevant_lines": "<line range or null>"
    }}
  ],
  "reasoning_trace": "<step-by-step chain of thought explaining your full analysis>"
}}

Return 2 to 5 suspect source files (do NOT rank test files as root cause), ordered from most to least likely root cause. \
The first entry must be your strongest candidate where the defective calculation or comparison actually occurs."""


PATCH_SYSTEM_PROMPT = """\
You are an expert software repair agent. Given a root-cause analysis, suspect files, \
and relevant source code, generate a MINIMAL fix as a unified diff.

Key principles:
1. Change as few lines as possible — this is a surgical fix, not a refactor.
2. The diff must be syntactically valid and directly applicable with `patch` or `git apply`.
3. Do NOT modify test files — fix only the source code that contains the defect.
4. Provide a clear, one-paragraph plain-English explanation of what was wrong and how you fixed it.

You MUST respond with ONLY a valid JSON object (no markdown fences, no commentary outside the JSON)."""


def build_patch_prompt(
    suspect_files: list,
    file_contents: dict,
    stack_trace: str,
    hypothesis: str,
    runtime: str,
) -> str:
    """Builds the patch generation user prompt."""

    suspects_section = ""
    for s in suspect_files:
        suspects_section += f"\n  Rank {s.rank}: {s.file_path} (confidence: {s.confidence})\n"
        suspects_section += f"    Reasoning: {s.reasoning}\n"
        suspects_section += f"    Suspected defect: {s.suspected_defect}\n"

    files_section = ""
    for path, content in file_contents.items():
        files_section += f"\n--- FILE: {path} ---\n{content}\n--- END FILE ---\n"

    return f"""\
RUNTIME: {runtime}

ROOT CAUSE HYPOTHESIS:
{hypothesis}

SUSPECT FILES (ranked):
{suspects_section}

SOURCE FILES:
{files_section}

STACK TRACE:
```
{stack_trace}
```

TASK: Generate a minimal unified diff that fixes the root cause. Change only what is necessary.

Respond with this exact JSON structure:
{{
  "target_file": "<path of the file to patch>",
  "unified_diff": "<complete unified diff string>",
  "explanation": "<one paragraph explaining what was wrong and how this fix resolves it>",
  "confidence": <float 0.0-1.0>
}}"""
