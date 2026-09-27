"""
Phase 2 Verification: Navigation Layer
Tests the NAVIGATE state against both hero repos using ONLY the Phase 1 stack_trace
output as input — no hints at the answer.

Produces:
1. Ranked suspect list for hero_python
2. Ranked suspect list for hero_node
3. Whether true root-cause file lands in top 3

Ground truth:
  - Python: order_service/discount.py
  - Node:   src/token_validator.js
"""

import os
import sys
import json
import time
import logging

# Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

# Reconfigure console output to UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, "..", "Evie", ".env"))  # Load GEMINI_API_KEY

from llm import get_llm_adapter
from orchestrator.navigator import navigate

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("phase2_verify")

# Load Phase 1 results
PHASE1_RESULTS_PATH = os.path.join(BASE_DIR, "phase1_verification_results.json")
with open(PHASE1_RESULTS_PATH, "r") as f:
    phase1 = json.load(f)

# Ground truth for evaluation
GROUND_TRUTH = {
    "python": "order_service/discount.py",
    "node": "src/token_validator.js",
}


def verify_hero(
    label: str,
    repo_subdir: str,
    runtime: str,
    phase1_result: dict,
    ground_truth_file: str,
):
    print(f"\n{'=' * 70}")
    print(f"  NAVIGATE Verification: {label}")
    print(f"{'=' * 70}")

    repo_path = os.path.join(BASE_DIR, "test_repos", repo_subdir)
    stack_trace = phase1_result["stack_trace"]

    print(f"\nInput stack trace (from Phase 1):")
    print(f"  {stack_trace[:200]}...")
    print(f"\nGround truth root-cause file: {ground_truth_file}")

    # Get LLM adapter (defaults to BobAdapter when BOB_API_KEY is present)
    llm = get_llm_adapter()
    print(f"LLM Adapter: {llm.get_model_id()}")

    # Collect emitted events
    emitted_events = []
    def on_event(event):
        emitted_events.append(event)
        msg = event.get("message", "")
        if msg:
            print(f"  [{event['event_type']}] {msg}")

    # Run navigation
    start = time.time()
    result, events = navigate(
        llm=llm,
        stack_trace=stack_trace,
        repo_path=repo_path,
        runtime=runtime,
        emit_event=on_event,
    )
    duration = round(time.time() - start, 2)

    print(f"\nNavigation completed in {duration}s")
    print(f"Model: {result.model_id}")
    print(f"Suspects returned: {len(result.suspects)}")

    # Print ranked suspects
    print(f"\n--- Ranked Suspect Files ---")
    ground_truth_rank = None
    for s in result.suspects:
        # Normalize path separators for comparison
        norm_path = s.file_path.replace("\\", "/")
        norm_gt = ground_truth_file.replace("\\", "/")
        is_gt = "  <<<< GROUND TRUTH" if norm_path == norm_gt else ""
        if norm_path == norm_gt:
            ground_truth_rank = s.rank
        print(f"  #{s.rank} [{s.confidence:.2f}] {s.file_path}{is_gt}")
        print(f"       Reasoning: {s.reasoning[:120]}...")
        print(f"       Suspected defect: {s.suspected_defect[:120]}...")
        print()

    print(f"--- Reasoning Trace ---")
    print(f"  {result.reasoning_trace[:500]}...")

    # Evaluate
    in_top_3 = ground_truth_rank is not None and ground_truth_rank <= 3
    print(f"\n{'=' * 70}")
    print(f"  RESULT: Ground truth '{ground_truth_file}' ", end="")
    if ground_truth_rank is not None:
        print(f"found at rank #{ground_truth_rank} {'[TOP 3 PASS]' if in_top_3 else '[NOT IN TOP 3 FAIL]'}")
    else:
        print(f"NOT FOUND in suspect list [FAIL]")
    print(f"{'=' * 70}")

    return {
        "label": label,
        "runtime": runtime,
        "ground_truth_file": ground_truth_file,
        "ground_truth_rank": ground_truth_rank,
        "in_top_3": in_top_3,
        "suspects": [s.to_dict() for s in result.suspects],
        "reasoning_trace": result.reasoning_trace,
        "model_id": result.model_id,
        "duration_seconds": duration,
        "events_emitted": len(events),
        "event_types_emitted": list(set(e["event_type"] for e in events)),
    }


def main():
    print("\n" + "#" * 70)
    print("  Phase 2 Verification: Navigation Layer")
    print("#" * 70)

    # Hero Python
    py_result = verify_hero(
        label="Hero Python (order_service VIP discount bug)",
        repo_subdir="hero_python",
        runtime="python",
        phase1_result=phase1["python_hero_result"],
        ground_truth_file=GROUND_TRUTH["python"],
    )

    # Hero Node
    node_result = verify_hero(
        label="Hero Node.js (token_validator clock skew bug)",
        repo_subdir="hero_node",
        runtime="node",
        phase1_result=phase1["node_hero_result"],
        ground_truth_file=GROUND_TRUTH["node"],
    )

    # Summary
    output = {
        "phase": "Phase 2 - Navigation Layer Verification",
        "python_navigation": py_result,
        "node_navigation": node_result,
        "both_in_top_3": py_result["in_top_3"] and node_result["in_top_3"],
    }

    results_file = os.path.join(BASE_DIR, "phase2_verification_results.json")
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'#' * 70}")
    print(f"  Phase 2 Final Summary")
    print(f"{'#' * 70}")
    print(f"  Python ground truth in top 3: {py_result['in_top_3']}")
    print(f"  Node   ground truth in top 3: {node_result['in_top_3']}")
    print(f"  BOTH IN TOP 3: {output['both_in_top_3']}")
    print(f"  Results saved to: {results_file}")

    if not output["both_in_top_3"]:
        print("\n  [WARNING] Not all ground-truth files landed in top 3.")
        print("  Navigation quality must be improved before proceeding to PATCH.")
        sys.exit(1)
    else:
        print("\n  [SUCCESS] Both hero bugs have true root cause in top 3 suspects!")
        sys.exit(0)


if __name__ == "__main__":
    main()
