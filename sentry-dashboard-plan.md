# Sentry Dashboard — Implementation Plan

## Top-Level Overview

Build a single-page Next.js (App Router) + Tailwind CSS dashboard at `frontend/` that:

1. Accepts a repo URL + failing test command from the user
2. Connects via WebSocket to a thin Python WebSocket server (added to `backend/`) that wraps `SentryOrchestrator`
3. Streams and renders live events in the canonical schema: `{event_type, state, timestamp, message, data}`
4. Renders each event as a human-readable live log with clear state-transition headings
5. Displays a unified diff viewer for the generated patch
6. Shows a before/after test-count summary panel at the end

The backend is a new `backend/main.py` FastAPI application that exposes `@app.websocket("/ws")` and bridges the orchestrator's `emit_callback` to the socket connection. No auth, no persistence, single active session.

The frontend uses real event sequences from `phase3_verification_results.json` as mock data during development before wiring the live WebSocket.

---

## Architecture Diagram (described)

```
User (browser)
   │  WebSocket ws://localhost:8000/ws
   ▼
backend/main.py  (FastAPI app, @app.websocket("/ws"), uvicorn)
   │  emit_callback
   ▼
SentryOrchestrator (backend/orchestrator/state_machine.py)
   │  events: {event_type, state, timestamp, message, data}
   ▼
frontend/  (Next.js App Router, Tailwind)
   ├── Input form (repo URL + test command)
   ├── State timeline bar (INGEST → … → PR_CREATE or REPORT_BEST_EFFORT)
   ├── Live event log (streaming, each event as a log line)
   ├── Diff viewer panel (patch_generated events, unified diff)
   └── Test summary panel (before/after counts, pass/fail badge)
```

---

## Sub-Tasks

---

### Sub-Task 1 — Backend FastAPI App + WebSocket Endpoint

**Status:** `[x] done`

**Intent:**
Create `backend/main.py` — a new FastAPI application that exposes a single `@app.websocket("/ws")` endpoint. There is no existing FastAPI app in the backend; this file brings one into existence. The WebSocket handler receives a JSON start message `{repo_url, test_cmd, runtime}`, runs `SentryOrchestrator` in a `ThreadPoolExecutor` (because the orchestrator is fully synchronous), and streams each emitted event as a JSON string back over the socket. The app is started with `uvicorn backend.main:app` from the repo root — one process, one port, one thing to start for the demo.

**Expected Outcomes:**
- `uvicorn backend.main:app --reload` starts on `http://localhost:8000`; the WebSocket is reachable at `ws://localhost:8000/ws`
- A client can connect, send `{"repo_url": "...", "test_cmd": "...", "runtime": "python"}`, and receive a stream of canonical event JSON strings
- Each event has the exact shape `{event_type, state, timestamp, message, data}`
- Server sends a final `{"event_type": "done", "state": "DONE", "timestamp": "...", "message": "Pipeline complete.", "data": {}}` frame when the run finishes, then closes the connection cleanly
- No auth, no multi-session handling; concurrent connections are not a concern

**Todo List:**
1. Create `backend/main.py`
2. Import `FastAPI`, `WebSocket` from `fastapi`; import `asyncio`, `json`, `concurrent.futures`; import `SentryOrchestrator` from `orchestrator.state_machine`
3. Instantiate `app = FastAPI()`
4. Define `@app.websocket("/ws")` handler: `async def ws_endpoint(websocket: WebSocket)`
5. In the handler: `await websocket.accept()`, then `await websocket.receive_text()` to get the start message; parse JSON and validate `repo_url` and `test_cmd` fields
6. Create a thread-safe emit callback: define `def emit(event)` that calls `asyncio.run_coroutine_threadsafe(websocket.send_text(json.dumps(event)), loop)` where `loop = asyncio.get_event_loop()`
7. Run the orchestrator in a `ThreadPoolExecutor`: `await loop.run_in_executor(executor, lambda: orchestrator.run(repo_url, test_cmd, runtime, emit_callback=emit))`
8. After the executor future resolves, send the final `done` frame and close
9. Add `fastapi`, `uvicorn[standard]` to a new `backend/requirements-api.txt`

**Relevant Context:**
- `backend/orchestrator/state_machine.py` — `SentryOrchestrator`, `emit_callback` pattern (lines 91-108)
- `backend/orchestrator/events.py` — canonical event shape
- `backend/test_patch_validate_phase3.py` — example of how to call `orchestrator.run()`
- No existing `main.py` or FastAPI instance exists anywhere in `backend/`

---

### Sub-Task 2 — Next.js Project Scaffold

**Status:** `[x] done`

**Intent:**
Scaffold a Next.js 14 App Router project at `frontend/` with Tailwind CSS, TypeScript, and the npm packages needed for the diff viewer and WebSocket client. No routing beyond the single root page is needed.

**Expected Outcomes:**
- `frontend/` directory exists with a valid Next.js App Router project
- `npm run dev` starts the dev server on port 3000
- Tailwind is configured and a smoke-test style works
- The following packages are present: `react-diff-viewer-continued` (unified diff display), `lucide-react` (icons)
- No ESLint errors on a fresh scaffold

**Todo List:**
1. Run `npx create-next-app@latest frontend --typescript --tailwind --app --no-src-dir --import-alias "@/*"` (non-interactive via `--yes` or by pre-setting answers)
2. `cd frontend && npm install react-diff-viewer-continued lucide-react`
3. Remove the boilerplate content from `frontend/app/page.tsx` (replace with `<main>Sentry Dashboard</main>`)
4. Verify `npm run dev` starts without errors

**Relevant Context:**
- No existing frontend — greenfield
- Target: Next.js 14, Tailwind CSS 3, TypeScript strict mode

---

### Sub-Task 3 — Mock Event Data Module

**Status:** `[x] done`

**Intent:**
Create `frontend/lib/mockEvents.ts` that exports two pre-baked event sequences — one for the Python hero run (success, PR_CREATE) and one for the honest-failure run (REPORT_BEST_EFFORT) — extracted directly from `phase3_verification_results.json`. This lets all UI components be built and tested with realistic data before the WebSocket is wired.

**Expected Outcomes:**
- `PYTHON_MOCK_EVENTS` and `FAILURE_MOCK_EVENTS` arrays are exported from `frontend/lib/mockEvents.ts`
- Each element is typed as `OrchestratorEvent` (defined in `frontend/lib/types.ts`)
- Both arrays include all event types present in the phase3 JSON: `state_transition`, `reasoning_step`, `suspect_ranking`, `patch_generated`, `validation_result`

**Todo List:**
1. Create `frontend/lib/types.ts` — define `OrchestratorEvent`, `SuspectFile`, `BeforeAfterCounts`, `AttemptRecord`, `RunResult`, `BestEffortReportData` TypeScript interfaces matching the backend schemas
2. Create `frontend/lib/mockEvents.ts`:
   - `PYTHON_MOCK_EVENTS`: copy the `python_hero_run.events` array verbatim from `phase3_verification_results.json` (lines 59–355); this is a real `.events[]` array with all 8+ event types
   - `NODE_MOCK_EVENTS`: copy the `node_hero_run.events` array verbatim (lines 356–707); also a real `.events[]` array, fixed=true
   - `FAILURE_MOCK_EVENTS`: **synthesise** from `honest_failure_fallback_verification` — this key has no `.events[]` array, only `best_effort_report.attempt_history`; construct a plausible event sequence manually using the attempt_history records and the canonical event shapes from `backend/orchestrator/events.py`
3. Export a `MOCK_SCENARIOS` constant: `{ python: PYTHON_MOCK_EVENTS, node: NODE_MOCK_EVENTS, failure: FAILURE_MOCK_EVENTS }`

**Relevant Context:**
- `phase3_verification_results.json` top-level keys (verified): `"phase"`, `"python_hero_run"`, `"node_hero_run"`, `"honest_failure_fallback_verification"`
- `python_hero_run.events` and `node_hero_run.events` are real arrays; `honest_failure_fallback_verification` has **no `.events` field** — only `best_effort_report.attempt_history`
- `backend/orchestrator/events.py` — authoritative field names and values for enums; use these to synthesise the failure event sequence

---

### Sub-Task 4 — Core UI Components

**Status:** `[x] done`

**Intent:**
Build the reusable UI components that compose the dashboard. These are all presentational — they receive props and render, no WebSocket logic. Each component must clearly represent its state so the event stream becomes the demo centerpiece.

**Expected Outcomes:**
The following components exist under `frontend/components/`:

- `StateTimeline` — horizontal pill-bar showing 8 states; active state is highlighted, completed states are checked, future states are dimmed
- `EventLog` — scrollable list of log lines; each line shows timestamp, a colored state badge, and the `message`; `state_transition` events get a full-width divider with the new state name; auto-scrolls to bottom
- `SuspectList` — shows ranked suspect files from a `suspect_ranking` event; each row has rank, filename, confidence bar, reasoning text (truncated/expandable)
- `DiffViewer` — wraps `react-diff-viewer-continued` with the unified diff from a `patch_generated` event; shows filename and attempt number in a header
- `TestSummary` — before/after counts in a two-column card: left = "Before" (red badge for failures), right = "After" (green badge for all-pass or remaining failures)
- `BestEffortReport` — shown when `final_state === REPORT_BEST_EFFORT`; shows `attempts_exhausted`, `best_hypothesis`, attempt history table

**Todo List:**
1. Create `frontend/components/StateTimeline.tsx` — props: `currentState: string`, `completedStates: string[]`; use the ordered 8-state constant from `types.ts`
2. Create `frontend/components/EventLog.tsx` — props: `events: OrchestratorEvent[]`; use `useEffect` with a ref to auto-scroll
3. Create `frontend/components/SuspectList.tsx` — props: from `suspect_ranking` event's `data.suspects`
4. Create `frontend/components/DiffViewer.tsx` — props: `diff: string`, `filename: string`, `attempt: number`; parse unified diff into old/new strings for `react-diff-viewer-continued`; for the library, use `splitView={false}` (unified mode)
5. Create `frontend/components/TestSummary.tsx` — props: `before: BeforeAfterCounts`, `after: BeforeAfterCounts`, `fixed: boolean`
6. Create `frontend/components/BestEffortReport.tsx` — props: `report: BestEffortReportData`

**Relevant Context:**
- `phase3_verification_results.json` for exact prop shapes
- `react-diff-viewer-continued` docs: accepts `oldValue` and `newValue` as strings; for split unified diff parsing, extract `-` lines as old and `+` lines as new, stripping the prefix character

---

### Sub-Task 5 — Dashboard Page and WebSocket Integration

**Status:** `[x] done`

**Intent:**
Wire all components together in `frontend/app/page.tsx`. The page has three views:
1. **Idle** — input form (repo URL, test command, runtime selector, a "Run Sentry" button, and a "Demo (mock)" button)
2. **Running** — live event log + state timeline updating in real time from WebSocket; diff viewer and suspects appear as their events arrive
3. **Done** — all panels visible, WebSocket closed, test summary shown

**Expected Outcomes:**
- Clicking "Demo (mock)" replays the Python mock events at 120ms intervals without a WebSocket, producing an animated live-log demo
- Clicking "Run Sentry" opens a real WebSocket to `ws://localhost:8000/ws`, sends the form values as JSON, and renders events as they arrive
- State machine drives rendering: `StateTimeline` updates on every `state_transition` event; `DiffViewer` appears on first `patch_generated` event; `TestSummary` appears when a terminal state is reached
- Page is a single scrollable column, mobile-readable, dark or light Tailwind theme

**Todo List:**
1. Create `frontend/app/page.tsx` — client component (`"use client"`)
2. Add state hooks: `events`, `currentState`, `suspects`, `diff`, `testSummary`, `sessionStatus` (`idle | running | done | error`)
3. Implement `handleMockRun()` — iterates `PYTHON_MOCK_EVENTS` with `setInterval` at 120ms, dispatches each event through a shared `processEvent(event)` function
4. Implement `handleLiveRun()` — creates `new WebSocket("ws://localhost:8000/ws")`, on `message` parses JSON and calls `processEvent(event)`, on `close`/`error` sets status accordingly
5. Implement `processEvent(event: OrchestratorEvent)` — appends to `events`, updates `currentState` on `state_transition`, extracts `suspects` from `suspect_ranking`, extracts `diff`/`filename`/`attempt` from `patch_generated`, extracts `before`/`after` counts from `validation_result`/`reasoning_step` with count data
6. Render idle form when `sessionStatus === 'idle'`
7. Render running/done layout: `StateTimeline` at top, two-column body (left = `EventLog` 60%, right = collapsible panels for `SuspectList`, `DiffViewer`, `TestSummary`, `BestEffortReport`)
8. Add a "Reset" button that clears all state back to idle
9. Ensure `EventLog` auto-scrolls as events arrive

**Relevant Context:**
- `frontend/lib/mockEvents.ts` — mock event arrays (Sub-Task 3)
- `frontend/components/` — all components (Sub-Task 4)
- `backend/main.py` — FastAPI WebSocket endpoint (Sub-Task 1)

---

### Sub-Task 6 — Polish and Validation

**Status:** `[x] done`

**Intent:**
Ensure the demo is legible, stable, and production-quality for a demo session. Fix any TypeScript errors, Tailwind issues, and ensure the mock replay works end-to-end without a backend.

**Expected Outcomes:**
- `npm run build` passes with zero TypeScript errors and zero ESLint errors
- The mock demo (`"Demo (mock)"` button) plays through all 8 states visually and terminates cleanly at `PR_CREATE`
- The failure scenario can also be demoed (add a second demo button or scenario selector)
- `DiffViewer` renders a visually clear before/after with `react-diff-viewer-continued`
- `StateTimeline` accurately reflects the current active state and marks prior states as complete
- The page title is "Sentry — CI/CD Autonomous Repair" with a favicon

**Todo List:**
1. Fix any TypeScript strict-mode errors surfaced by `npm run build`
2. Add `<title>` and `<meta description>` to `frontend/app/layout.tsx`
3. Add a second demo button: "Demo (failure scenario)" that replays `FAILURE_MOCK_EVENTS`
4. Verify `react-diff-viewer-continued` renders without SSR issues (wrap in `dynamic()` with `ssr: false` if needed)
5. Verify the `EventLog` auto-scroll works correctly in both mock and live modes
6. Run `npm run build` and resolve all errors

**Relevant Context:**
- `frontend/lib/mockEvents.ts` — both mock scenarios
- Next.js `dynamic()` import for client-only libraries

---

## Implementation Order

```
Sub-Task 1 (WS server) ──────────────────────────────────┐
Sub-Task 2 (scaffold) → Sub-Task 3 (types/mock data)     │
                      → Sub-Task 4 (components)           │
                      → Sub-Task 5 (page + WS integration)┘
                      → Sub-Task 6 (polish + build)
```

Sub-Tasks 1 and 2 can begin in parallel. Sub-Tasks 3, 4, and 5 depend on 2. Sub-Task 6 depends on all others.

---

## Key Constraints and Decisions

| Concern | Decision |
|---|---|
| WebSocket server | New `backend/main.py` — FastAPI app with `@app.websocket("/ws")`; run via `uvicorn backend.main:app`; no existing app to extend |
| Diff viewer library | `react-diff-viewer-continued` (fork of `react-diff-viewer`, maintained, works with Next 14) |
| Mock data source | Extracted directly from `phase3_verification_results.json` — no invented data |
| SSR for diff viewer | Wrap in `next/dynamic` with `ssr: false` to avoid `window` errors |
| State ordering | Canonical: INGEST → REPRODUCE → NAVIGATE → HYPOTHESIZE → PATCH → VALIDATE → PR_CREATE / REPORT_BEST_EFFORT |
| Tailwind theme | Dark background (slate-950) to make colored state badges pop — feels like a real CI dashboard |
| No auth/persistence | Confirmed — single session, page reload clears everything |
