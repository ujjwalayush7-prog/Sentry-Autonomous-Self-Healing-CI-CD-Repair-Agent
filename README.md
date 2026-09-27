# ⬡ SENTRY — Autonomous Self-Healing CI/CD Repair Agent

> **Built with IBM Bob 2.0 Gateway & IBM Granite (`granite-8b-code-instruct`)**  
> Reproduces failing CI/CD builds in isolated sandboxes, traces root causes up to 4 hops deep across AST & import graphs, validates surgical patches in a closed loop, and opens verified GitHub Pull Requests autonomously.

---

## 🚨 The Problem: The "Assertion Proximity" Trap

When a CI/CD pipeline breaks, engineering teams lose hours to manual triage and context-switching. Worse, **where a test assertion fails is almost never where the bug actually lives**:
- A test fails in `tests/test_pricing.py`, which calls `order_service/pricing.py`, which imports `order_service/discount.py`.
- Naive AI coding assistants only inspect the failing test file, hallucinate unverified diffs, or delete test assertions just to force a green build.

## 💡 The Solution: Sentry

**Sentry** is a deterministic, closed-loop autonomous repair agent that heals broken CI/CD pipelines without human intervention:

1. **`INGEST` & `REPRODUCE`**: Clones the repository into an isolated sandbox (`DockerSandbox` or `LocalSandbox`) and runs the test suite (`pytest`, `unittest`, `node --test`, `Jest`) to capture baseline counts and stack traces.
2. **`NAVIGATE` (4-Hop AST & Import Graph)**: Extracts stack frames and traverses Python & Node.js module imports up to **4 hops deep**, feeding the call chain to **IBM Granite (`granite-8b-code-instruct`)** via the **IBM Bob 2.0 Gateway** while strictly forbidding modifications to test files.
3. **`HYPOTHESIZE` & `PATCH`**: Ranks suspect files by confidence score and generates a minimal, surgical unified diff targeting the root-cause source file.
4. **`VALIDATE` (Closed-Loop Retry up to 3 Attempts)**: Applies the patch and re-executes the full test suite inside the sandbox. If validation fails, Sentry cleanly reverts the workspace (`git checkout -- .`) and feeds the new error trace back into the model.
5. **`PR_CREATE` vs. `REPORT_BEST_EFFORT` (Anti-Hallucination Guarantee)**:
   - **RED → GREEN**: Automatically cuts a fix branch (`sentry/fix-...`), pushes to GitHub, and opens a Pull Request containing a full before/after verification matrix.
   - **Unresolved after 3 Attempts**: Never fabricates success. Compiles an **Honest Best-Effort Diagnostic Report** with ranked suspects, attempted diffs, and root-cause hypotheses for human engineers.

---

## 🏗️ Architecture

```text
Next.js 14 Dashboard (App Router, Tailwind CSS, Unified Diff Viewer)
        │  WebSocket (ws://localhost:8000/ws)
        ▼
FastAPI WebSocket Bridge (backend/main.py)
        │  Real-time canonical event stream
        ▼
SentryOrchestrator 8-State Finite State Machine (backend/orchestrator/state_machine.py)
  INGEST ──► REPRODUCE ──► NAVIGATE ──► HYPOTHESIZE ──► PATCH ◄──► VALIDATE
                                                                     │
                                            ┌────────────────────────┴────────────────────────┐
                                            ▼ (100% Tests Pass)                               ▼ (3 Attempts Exhausted)
                                        PR_CREATE                                    REPORT_BEST_EFFORT
                                  (GitHub REST API v3)                              (Honest Diagnostic Trail)
```

---

## 🚀 Quick Start

### 1. Backend (FastAPI + Sentry Orchestrator)
```bash
pip install -r backend/requirements-api.txt
uvicorn backend.main:app --reload --port 8000
```

### 2. Frontend (Next.js 14 Live Command Center)
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` to run live repairs or replay verified benchmarks (`▶ Python fix`, `▶ Node fix`, `⚡ Failure`).

---

## ✅ Verified End-to-End Benchmarks

| Benchmark | Runtime | Root-Cause File (2 Hops Deep) | Before | After | Result |
|---|---|---|---|---|---|
| **`hero_python`** | Python (`pytest`) | `order_service/discount.py` (90% conf) | 3 Passed, 1 Failed (RED) | **4 Passed, 0 Failed (GREEN)** | Fixed on Attempt 1 + GitHub PR Opened |
| **`hero_node`** | Node.js (`node --test`) | `src/token_validator.js` (92% conf) | 2 Passed, 1 Failed (RED) | **3 Passed, 0 Failed (GREEN)** | Fixed on Attempt 1 + GitHub PR Opened |
| **`honest_failure`** | Python (`pytest`) | Unfixable stub verification | 3 Passed, 1 Failed (RED) | Reverted cleanly after 3 attempts | Honest `REPORT_BEST_EFFORT` compiled |
