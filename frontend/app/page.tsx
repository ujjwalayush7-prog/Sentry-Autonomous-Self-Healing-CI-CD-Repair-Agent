"use client";

import { useState, useCallback, useRef } from "react";
import {
  OrchestratorEvent,
  AgentState,
  SuspectFile,
  TestCounts,
  BestEffortReportData,
  PIPELINE_STATES,
} from "@/lib/types";
import { MOCK_SCENARIOS, MockScenarioKey } from "@/lib/mockEvents";
import StateTimeline from "@/components/StateTimeline";
import EventLog from "@/components/EventLog";
import SuspectList from "@/components/SuspectList";
import DiffViewer from "@/components/DiffViewer";
import TestSummary from "@/components/TestSummary";
import BestEffortReport from "@/components/BestEffortReport";
import { RotateCcw, Wifi } from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type SessionStatus = "idle" | "running" | "done" | "error";

interface DiffState {
  diff: string;
  filename: string;
  attempt: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function Home() {
  // Form
  const [repoUrl, setRepoUrl] = useState("");
  const [testCmd, setTestCmd] = useState("");
  const [runtime, setRuntime] = useState<"python" | "node">("python");

  // Session
  const [status, setStatus] = useState<SessionStatus>("idle");
  const [statusMsg, setStatusMsg] = useState("");

  // Event stream
  const [events, setEvents] = useState<OrchestratorEvent[]>([]);
  const [currentState, setCurrentState] = useState<AgentState | null>(null);
  const [completedStates, setCompletedStates] = useState<AgentState[]>([]);

  // Derived panels
  const [suspects, setSuspects] = useState<SuspectFile[]>([]);
  const [diffState, setDiffState] = useState<DiffState | null>(null);
  const [beforeCounts, setBeforeCounts] = useState<TestCounts | null>(null);
  const [afterCounts, setAfterCounts] = useState<TestCounts | null>(null);
  const [fixed, setFixed] = useState(false);
  const [bestEffortReport, setBestEffortReport] = useState<BestEffortReportData | null>(null);

  // Refs
  const wsRef = useRef<WebSocket | null>(null);
  const mockTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ---------------------------------------------------------------------------
  // Core event processor — shared by mock and live modes
  // ---------------------------------------------------------------------------
  const processEvent = useCallback((ev: OrchestratorEvent) => {
    setEvents((prev) => [...prev, ev]);

    if (ev.event_type === "state_transition") {
      const newState = ev.state as AgentState;
      setCurrentState(newState);
      setCompletedStates((prev) => {
        const idx = PIPELINE_STATES.indexOf(newState);
        // All pipeline states before this index are complete
        const completed = PIPELINE_STATES.slice(0, idx);
        return Array.from(new Set([...prev, ...completed]));
      });
    }

    if (ev.event_type === "suspect_ranking" && ev.data?.suspects) {
      setSuspects(ev.data.suspects as SuspectFile[]);
    }

    if (ev.event_type === "patch_generated" && ev.data?.unified_diff) {
      setDiffState({
        diff: ev.data.unified_diff as string,
        filename: ev.data.target_file as string,
        attempt: ev.data.attempt as number,
      });
    }

    if (ev.event_type === "validation_result" && ev.data?.passed) {
      // Keep the latest successful validation's after counts
      setAfterCounts({
        tests_total: ev.data.tests_total as number,
        tests_passed: ev.data.tests_passed as number,
        tests_failed: ev.data.tests_failed as number,
      });
      setFixed(true);
    }

    if (ev.event_type === "reasoning_step") {
      // REPRODUCE step carries before_counts
      if (ev.data?.before_counts && !beforeCounts) {
        setBeforeCounts(ev.data.before_counts as TestCounts);
      }
      // VALIDATE step "RED -> GREEN" carries both
      if (ev.data?.after_counts) {
        setAfterCounts(ev.data.after_counts as TestCounts);
      }
    }

    if (ev.event_type === "best_effort_report") {
      setBestEffortReport(ev.data as BestEffortReportData);
      // Extract before counts from attempt_history if not already set
      if (!beforeCounts && ev.data?.attempt_history?.[0]) {
        const first = ev.data.attempt_history[0];
        setBeforeCounts({
          tests_total: first.tests_total as number,
          tests_passed: first.tests_passed as number,
          tests_failed: first.tests_failed as number,
        });
        setAfterCounts({
          tests_total: first.tests_total as number,
          tests_passed: first.tests_passed as number,
          tests_failed: first.tests_failed as number,
        });
      }
    }

    // Terminal "done" sentinel from backend/main.py
    if (ev.event_type === "done") {
      setStatus("done");
    }

    if (ev.event_type === "error") {
      setStatus("error");
      setStatusMsg(ev.message);
    }
  }, [beforeCounts]);

  // ---------------------------------------------------------------------------
  // Reset
  // ---------------------------------------------------------------------------
  const handleReset = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (mockTimerRef.current) {
      clearInterval(mockTimerRef.current);
      mockTimerRef.current = null;
    }
    setStatus("idle");
    setStatusMsg("");
    setEvents([]);
    setCurrentState(null);
    setCompletedStates([]);
    setSuspects([]);
    setDiffState(null);
    setBeforeCounts(null);
    setAfterCounts(null);
    setFixed(false);
    setBestEffortReport(null);
  }, []);

  // ---------------------------------------------------------------------------
  // Mock playback
  // ---------------------------------------------------------------------------
  const handleMockRun = useCallback(
    (scenario: MockScenarioKey) => {
      handleReset();
      setStatus("running");
      const sequence = MOCK_SCENARIOS[scenario];
      let idx = 0;

      const timer = setInterval(() => {
        if (idx >= sequence.length) {
          clearInterval(timer);
          mockTimerRef.current = null;
          setStatus("done");
          return;
        }
        processEvent(sequence[idx]);
        idx++;
      }, 120);

      mockTimerRef.current = timer;
    },
    [handleReset, processEvent]
  );

  // ---------------------------------------------------------------------------
  // Live WebSocket run
  // ---------------------------------------------------------------------------
  const handleLiveRun = useCallback(() => {
    if (!repoUrl.trim() || !testCmd.trim()) {
      setStatusMsg("Please enter a repo URL and test command.");
      return;
    }
    handleReset();
    setStatus("running");

    const ws = new WebSocket("ws://localhost:8000/ws");
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ repo_url: repoUrl.trim(), test_cmd: testCmd.trim(), runtime }));
    };

    ws.onmessage = (msg) => {
      try {
        const ev = JSON.parse(msg.data) as OrchestratorEvent;
        processEvent(ev);
      } catch {
        // ignore unparseable frames
      }
    };

    ws.onerror = () => {
      setStatus("error");
      setStatusMsg("WebSocket error — is the backend running? (uvicorn backend.main:app)");
    };

    ws.onclose = () => {
      if (status === "running") setStatus("done");
    };
  }, [repoUrl, testCmd, runtime, handleReset, processEvent, status]);

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------
  const isTerminal = status === "done" || status === "error";
  const showSidePanels = status !== "idle";

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>

      {/* ── Top bar ── */}
      <header
        className="px-6 py-3 flex items-center gap-3 shrink-0"
        style={{ borderBottom: "1px solid var(--border-subtle)", background: "var(--bg-surface)" }}
      >
        <div className="flex items-center gap-3">
          <span className="font-mono font-bold text-base tracking-tight" style={{ color: "var(--text-primary)" }}>
            ⬡ SENTRY
          </span>
          <span className="text-sm" style={{ color: "var(--text-dim)" }}>
            CI/CD Autonomous Repair
          </span>
        </div>

        {status !== "idle" && (
          <div className="ml-auto flex items-center gap-3">
            {/* Status pill */}
            <span
              className="text-[11px] font-mono px-2 py-0.5 rounded"
              style={{
                background:
                  status === "running" ? "var(--c-amber-bg)"
                  : status === "done"   ? "var(--c-green-bg)"
                  :                       "var(--c-red-bg)",
                color:
                  status === "running" ? "var(--c-amber)"
                  : status === "done"   ? "var(--c-green)"
                  :                       "var(--c-red)",
                border: `1px solid ${
                  status === "running" ? "var(--c-amber-border)"
                  : status === "done"   ? "var(--c-green-border)"
                  :                       "var(--c-red-border)"
                }`,
              }}
            >
              {status === "running" ? "● RUNNING" : status === "done" ? "● DONE" : "● ERROR"}
            </span>
            <button
              onClick={handleReset}
              className="flex items-center gap-1 text-xs transition-colors"
              style={{ color: "var(--text-secondary)" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
            >
              <RotateCcw className="w-3 h-3" />
              Reset
            </button>
          </div>
        )}
      </header>

      <main className="flex-1 flex flex-col gap-4 p-4 max-w-[1600px] mx-auto w-full">

        {/* ── Input form ── */}
        <section
          className={`rounded-lg p-4 transition-opacity ${status === "running" ? "opacity-50 pointer-events-none" : ""}`}
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
        >
          <div className="flex flex-wrap gap-3 items-end">
            {/* Repo URL */}
            <div className="flex-1 min-w-[240px]">
              <label className="block text-[11px] uppercase tracking-wider mb-1.5" style={{ color: "var(--text-secondary)" }}>
                Repo URL / path
              </label>
              <input
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/org/repo  or  /local/path"
                className="w-full rounded px-3 py-2 text-sm font-mono focus:outline-none transition-colors"
                style={{
                  background: "var(--bg-raised)",
                  border: "1px solid var(--border-subtle)",
                  color: "var(--text-primary)",
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = "var(--c-amber)")}
                onBlur={(e)  => (e.currentTarget.style.borderColor = "var(--border-subtle)")}
              />
            </div>

            {/* Test command */}
            <div className="flex-1 min-w-[160px]">
              <label className="block text-[11px] uppercase tracking-wider mb-1.5" style={{ color: "var(--text-secondary)" }}>
                Failing test command
              </label>
              <input
                value={testCmd}
                onChange={(e) => setTestCmd(e.target.value)}
                placeholder="pytest -v  or  node --test"
                className="w-full rounded px-3 py-2 text-sm font-mono focus:outline-none transition-colors"
                style={{
                  background: "var(--bg-raised)",
                  border: "1px solid var(--border-subtle)",
                  color: "var(--text-primary)",
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = "var(--c-amber)")}
                onBlur={(e)  => (e.currentTarget.style.borderColor = "var(--border-subtle)")}
              />
            </div>

            {/* Runtime */}
            <div>
              <label className="block text-[11px] uppercase tracking-wider mb-1.5" style={{ color: "var(--text-secondary)" }}>
                Runtime
              </label>
              <select
                value={runtime}
                onChange={(e) => setRuntime(e.target.value as "python" | "node")}
                className="rounded px-3 py-2 text-sm focus:outline-none"
                style={{
                  background: "var(--bg-raised)",
                  border: "1px solid var(--border-subtle)",
                  color: "var(--text-primary)",
                }}
              >
                <option value="python">Python</option>
                <option value="node">Node.js</option>
              </select>
            </div>

            {/* Run button */}
            <button
              onClick={handleLiveRun}
              className="flex items-center gap-2 px-4 py-2 rounded text-sm font-semibold transition-colors"
              style={{ background: "var(--bg-raised)", border: "1px solid var(--border-active)", color: "var(--text-primary)" }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--c-amber)"; e.currentTarget.style.color = "var(--c-amber)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border-active)"; e.currentTarget.style.color = "var(--text-primary)"; }}
            >
              <Wifi className="w-4 h-4" />
              Run Sentry
            </button>

            {/* Demo buttons */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>or demo:</span>
              <DemoButton label="▶ Python fix" onClick={() => handleMockRun("python")} />
              <DemoButton label="▶ Node fix"   onClick={() => handleMockRun("node")} />
              <DemoButton label="⚡ Failure"   onClick={() => handleMockRun("failure")} danger />
            </div>
          </div>

          {statusMsg && (
            <div className="mt-2 text-xs font-mono" style={{ color: "var(--c-red)" }}>{statusMsg}</div>
          )}
        </section>

        {/* ── Pipeline view ── */}
        {showSidePanels && (
          <>
            {/* State timeline */}
            <section
              className="rounded-lg px-5 py-4"
              style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
            >
              <StateTimeline currentState={currentState} completedStates={completedStates} />
            </section>

            {/* Two-column body */}
            <div className="flex gap-4 flex-1" style={{ minHeight: "60vh" }}>
              {/* Left: event log — 60% */}
              <div className="flex-[3] min-w-0 flex flex-col gap-1">
                <div
                  className="text-[10px] uppercase tracking-widest px-1"
                  style={{ color: "var(--text-dim)" }}
                >
                  Live event stream
                </div>
                <div className="flex-1" style={{ minHeight: "55vh" }}>
                  <EventLog events={events} />
                </div>
              </div>

              {/* Right: side panels — 40% */}
              <div className="flex-[2] min-w-0 space-y-3 overflow-y-auto" style={{ maxHeight: "80vh" }}>

                {suspects.length > 0 && (
                  <Panel title="Suspect Files">
                    <SuspectList suspects={suspects} />
                  </Panel>
                )}

                {/* Diff panel — focal point when present */}
                {diffState && (
                  <Panel title="Generated Patch" focal>
                    <DiffViewer
                      diff={diffState.diff}
                      filename={diffState.filename}
                      attempt={diffState.attempt}
                    />
                  </Panel>
                )}

                {isTerminal && beforeCounts && afterCounts && (
                  <Panel title="Test Summary">
                    <TestSummary before={beforeCounts} after={afterCounts} fixed={fixed} />
                  </Panel>
                )}

                {bestEffortReport && (
                  <Panel title="Diagnostic Report">
                    <BestEffortReport report={bestEffortReport} />
                  </Panel>
                )}
              </div>
            </div>
          </>
        )}

        {/* ── Idle placeholder ── */}
        {status === "idle" && (
          <div
            className="flex-1 flex items-center justify-center text-sm font-mono"
            style={{ color: "var(--text-dim)" }}
          >
            Enter a repo and test command, then click Run Sentry — or choose a demo above.
          </div>
        )}
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Panel wrapper — focal=true adds the diff glow class
// ---------------------------------------------------------------------------
function Panel({
  title,
  children,
  focal = false,
}: {
  title: string;
  children: React.ReactNode;
  focal?: boolean;
}) {
  return (
    <div
      className={`overflow-hidden rounded-lg transition-all duration-500 ${focal ? "diff-focal-panel" : ""}`}
      style={{
        background: "var(--bg-surface)",
        border: `1px solid var(--border-subtle)`,
      }}
    >
      <div
        className="px-3 py-2 text-[10px] font-semibold uppercase tracking-widest"
        style={{
          borderBottom: "1px solid var(--border-subtle)",
          color: focal ? "var(--c-amber)" : "var(--text-secondary)",
        }}
      >
        {title}
      </div>
      <div className="p-3">{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Demo button helper — avoids repeating inline hover handlers
// ---------------------------------------------------------------------------
function DemoButton({
  label,
  onClick,
  danger = false,
}: {
  label: string;
  onClick: () => void;
  danger?: boolean;
}) {
  const base   = danger ? "var(--c-red-bg)"  : "var(--bg-raised)";
  const border = danger ? "var(--c-red-border)" : "var(--border-subtle)";
  const color  = danger ? "var(--c-red)"     : "var(--text-secondary)";
  const hover  = danger ? "var(--c-red)"     : "var(--text-primary)";

  return (
    <button
      onClick={onClick}
      className="px-3 py-1.5 rounded text-xs font-mono transition-colors"
      style={{ background: base, border: `1px solid ${border}`, color }}
      onMouseEnter={(e) => { e.currentTarget.style.color = hover; e.currentTarget.style.borderColor = hover; }}
      onMouseLeave={(e) => { e.currentTarget.style.color = color; e.currentTarget.style.borderColor = border; }}
    >
      {label}
    </button>
  );
}
