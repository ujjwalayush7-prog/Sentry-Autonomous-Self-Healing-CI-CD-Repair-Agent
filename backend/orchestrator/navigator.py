"""
Navigator Module
Implements the NAVIGATE state of the orchestrator.
Takes Phase 1 sandbox output, builds LLM context (stack trace + file tree + source contents),
calls the LLM navigation adapter, and returns ranked suspect files with reasoning.
"""

import os
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from llm.base import BaseLLMAdapter, NavigationResult, SuspectFile
from orchestrator.events import (
    AgentState,
    reasoning_step_event,
    suspect_ranking_event,
)

logger = logging.getLogger(__name__)


def get_file_tree(repo_path: str) -> str:
    """
    Generates a simple text file tree of the repository,
    excluding .git, node_modules, __pycache__, .pytest_cache, etc.
    """
    EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache",
                    ".tox", ".venv", "venv", "dist", "build", ".eggs", "*.egg-info"}
    EXCLUDE_FILES = {".gitignore", ".DS_Store", "Thumbs.db"}

    lines = []
    repo_path = os.path.abspath(repo_path)

    for root, dirs, files in os.walk(repo_path):
        # Filter excluded directories in-place
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.endswith(".egg-info")]

        level = root.replace(repo_path, "").count(os.sep)
        indent = "  " * level
        dir_name = os.path.basename(root)
        lines.append(f"{indent}{dir_name}/")

        sub_indent = "  " * (level + 1)
        for f in sorted(files):
            if f not in EXCLUDE_FILES:
                lines.append(f"{sub_indent}{f}")

    return "\n".join(lines)


def extract_referenced_files(stack_trace: str, repo_path: str) -> List[str]:
    """
    Extracts file paths referenced in a stack trace.
    Returns paths relative to repo root.
    """
    import re

    # Patterns for various stack trace formats:
    # Python: File "path/to/file.py", line N
    # Node:   at Something (path/to/file.js:N:N)
    # Also:   path/file.ext:N: ErrorType
    patterns = [
        r'File "([^"]+)"',           # Python traceback
        r'at\s+\S+\s+\(([^)]+?):\d+:\d+\)',  # Node.js (at Func (file:line:col))
        r'at\s+([^\s:]+\.(?:js|ts|mjs)):\d+:\d+',  # Node.js bare
        r'(\S+\.(?:py|js|ts|mjs)):\d+',  # Generic file:line
    ]

    found_files = set()
    abs_repo = os.path.abspath(repo_path)

    for pattern in patterns:
        for match in re.finditer(pattern, stack_trace):
            filepath = match.group(1)
            # Normalize and make relative
            filepath = filepath.replace("\\", "/")

            # Try to resolve to a repo-relative path
            if os.path.isabs(filepath):
                # If it's under a temp dir (sandbox), try to extract the relative part
                # e.g., /tmp/sentry_sandbox_xyz/tests/test_pricing.py -> tests/test_pricing.py
                parts = filepath.split("/")
                for i, part in enumerate(parts):
                    candidate = "/".join(parts[i:])
                    full_candidate = os.path.join(abs_repo, candidate.replace("/", os.sep))
                    if os.path.exists(full_candidate):
                        found_files.add(candidate)
                        break
            else:
                full_path = os.path.join(abs_repo, filepath.replace("/", os.sep))
                if os.path.exists(full_path):
                    found_files.add(filepath)

    return list(found_files)


def collect_source_files(repo_path: str, referenced_files: List[str], max_hops: int = 4) -> Dict[str, str]:
    """
    Reads the contents of referenced files plus transitive imports (up to max_hops).
    Handles:
      - Python absolute imports (from pkg.mod import x, import pkg.mod)
      - Python relative imports (from .mod import x)
      - Node CommonJS require('./mod') and ES import ... from './mod'
    Returns a dict of {relative_path: content}.
    """
    import re

    abs_repo = os.path.abspath(repo_path)
    contents: Dict[str, str] = {}

    def _read_rel(rel_p: str) -> None:
        norm_rel = rel_p.replace("\\", "/").lstrip("/")
        if norm_rel in contents:
            return
        full_p = os.path.join(abs_repo, norm_rel.replace("/", os.sep))
        if os.path.isfile(full_p):
            try:
                with open(full_p, "r", encoding="utf-8", errors="replace") as f:
                    contents[norm_rel] = f.read()
            except Exception as e:
                logger.warning(f"Could not read {full_p}: {e}")

    for rel_path in referenced_files:
        _read_rel(rel_path)

    # Transitive BFS over imported modules
    visited = set()
    for _ in range(max_hops):
        current_items = [(k, v) for k, v in list(contents.items()) if k not in visited]
        if not current_items:
            break

        for rel_path, content in current_items:
            visited.add(rel_path)
            file_dir = os.path.dirname(os.path.join(abs_repo, rel_path.replace("/", os.sep)))

            # 1. Python imports: from X import Y  or  import X
            py_matches = list(re.finditer(r"from\s+(\.*[\w.]+)\s+import\s+([\w, *]+)", content))
            for m in py_matches:
                mod_spec = m.group(1)
                imported_names = [n.strip() for n in m.group(2).split(",")]
                if mod_spec.startswith("."):
                    # Relative import: count leading dots
                    dots = len(mod_spec) - len(mod_spec.lstrip("."))
                    remainder = mod_spec.lstrip(".").replace(".", os.sep)
                    base_dir = file_dir
                    for _ in range(dots - 1):
                        base_dir = os.path.dirname(base_dir)
                    candidates = [os.path.join(base_dir, remainder + ".py")]
                    for name in imported_names:
                        candidates.append(os.path.join(base_dir, remainder, name + ".py"))
                else:
                    mod_path = mod_spec.replace(".", os.sep)
                    candidates = [os.path.join(abs_repo, mod_path + ".py")]
                    for name in imported_names:
                        candidates.append(os.path.join(abs_repo, mod_path, name + ".py"))

                for cand in candidates:
                    if os.path.isfile(cand):
                        rel = os.path.relpath(cand, abs_repo).replace(os.sep, "/")
                        _read_rel(rel)

            # 2. Node CommonJS require('./...') and ES import ... from './...'
            js_matches = list(re.finditer(r"(?:require\(|from\s+)['\"]([./][^'\"]+)['\"]", content))
            for m in js_matches:
                req_path = m.group(1)
                resolved = os.path.normpath(os.path.join(file_dir, req_path))
                for ext in [".js", ".ts", ".mjs", ""]:
                    cand = resolved + ext
                    if os.path.isfile(cand):
                        rel = os.path.relpath(cand, abs_repo).replace(os.sep, "/")
                        _read_rel(rel)
                        break

    return contents


def navigate(
    llm: BaseLLMAdapter,
    stack_trace: str,
    repo_path: str,
    runtime: str,
    emit_event: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Tuple[NavigationResult, List[Dict[str, Any]]]:
    """
    Execute the NAVIGATE state: analyze stack trace, build context, call LLM,
    return ranked suspects.

    Args:
        llm: LLM adapter instance
        stack_trace: Structured stack trace from Phase 1
        repo_path: Path to the repository root
        runtime: 'python' or 'node'
        emit_event: Optional callback to emit WebSocket events in real-time

    Returns:
        (NavigationResult, list of events emitted)
    """
    events = []

    def emit(event):
        events.append(event)
        if emit_event:
            emit_event(event)

    # Step 1: Build file tree
    emit(reasoning_step_event(
        AgentState.NAVIGATE, 1,
        "Building repository file tree...",
    ))
    file_tree = get_file_tree(repo_path)
    emit(reasoning_step_event(
        AgentState.NAVIGATE, 2,
        f"File tree built: {len(file_tree.splitlines())} entries",
        {"file_tree_preview": file_tree[:500]},
    ))

    # Step 2: Extract files referenced in stack trace
    referenced = extract_referenced_files(stack_trace, repo_path)
    emit(reasoning_step_event(
        AgentState.NAVIGATE, 3,
        f"Extracted {len(referenced)} files referenced in stack trace: {referenced}",
        {"referenced_files": referenced},
    ))

    # Step 3: Collect source file contents (referenced + their imports)
    file_contents = collect_source_files(repo_path, referenced)
    emit(reasoning_step_event(
        AgentState.NAVIGATE, 4,
        f"Collected source contents for {len(file_contents)} files (referenced + imports): "
        f"{list(file_contents.keys())}",
        {"files_loaded": list(file_contents.keys())},
    ))

    # Step 4: Call LLM navigation
    emit(reasoning_step_event(
        AgentState.NAVIGATE, 5,
        f"Calling LLM ({llm.get_model_id()}) for root-cause navigation...",
        {"model_id": llm.get_model_id()},
    ))

    result = llm.navigate(
        stack_trace=stack_trace,
        file_tree=file_tree,
        file_contents=file_contents,
        runtime=runtime,
    )

    # Step 5: Emit suspect ranking
    suspects_dicts = [s.to_dict() for s in result.suspects]
    ranking_event = suspect_ranking_event(
        suspects=suspects_dicts,
        reasoning_trace=result.reasoning_trace,
        files_analyzed=result.files_analyzed,
        model_id=result.model_id,
    )
    emit(ranking_event)

    emit(reasoning_step_event(
        AgentState.NAVIGATE, 6,
        f"Navigation complete. Top suspect: {result.suspects[0].file_path if result.suspects else 'none'} "
        f"(confidence: {result.suspects[0].confidence if result.suspects else 0.0})",
        {"top_suspect": result.suspects[0].to_dict() if result.suspects else None},
    ))

    return result, events
