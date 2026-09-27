"use client";

import { useEffect, useRef } from "react";
import { OrchestratorEvent } from "@/lib/types";

interface EventLogProps {
  events: OrchestratorEvent[];
}

// All state badges use the three-color system only.
// Active pipeline states → amber. Success terminal → green. Failure terminal → red.
// Everything else → neutral warm grey.
const STATE_BADGE_STYLE: Record<string, { bg: string; text: string }> = {
  INGEST:             { bg: "bg-[var(--bg-raised)]",    text: "text-[var(--text-secondary)]" },
  REPRODUCE:          { bg: "bg-[var(--bg-raised)]",    text: "text-[var(--text-secondary)]" },
  NAVIGATE:           { bg: "bg-[var(--bg-raised)]",    text: "text-[var(--text-secondary)]" },
  HYPOTHESIZE:        { bg: "bg-[var(--bg-raised)]",    text: "text-[var(--text-secondary)]" },
  PATCH:              { bg: "bg-[var(--c-amber-bg)]",   text: "text-[var(--c-amber)]"        },
  VALIDATE:           { bg: "bg-[var(--c-amber-bg)]",   text: "text-[var(--c-amber)]"        },
  PR_CREATE:          { bg: "bg-[var(--c-green-bg)]",   text: "text-[var(--c-green)]"        },
  REPORT_BEST_EFFORT: { bg: "bg-[var(--c-red-bg)]",     text: "text-[var(--c-red)]"          },
  DONE:               { bg: "bg-[var(--bg-raised)]",    text: "text-[var(--text-secondary)]" },
  ERROR:              { bg: "bg-[var(--c-red-bg)]",     text: "text-[var(--c-red)]"          },
};

// Per-event-type sigil (text, not emoji — keeps it terminal-clean)
const EVENT_SIGIL: Record<string, string> = {
  state_transition:   "──",
  reasoning_step:     " ·",
  suspect_ranking:    " ?",
  patch_generated:    " Δ",
  validation_result:  " ✓",
  pr_created:         " ✓",
  best_effort_report: " ⚠",
  error:              " ✗",
  log:                " ·",
  done:               " ■",
};

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString("en-US", { hour12: false });
  } catch {
    return ts.slice(11, 19) || ts;
  }
}

export default function EventLog({ events }: EventLogProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  return (
    <div
      className="h-full overflow-y-auto font-mono text-xs leading-relaxed p-2"
      style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px" }}
    >
      {events.length === 0 && (
        <div className="p-2" style={{ color: "var(--text-dim)", fontStyle: "italic" }}>
          Waiting for events…
        </div>
      )}

      {events.map((ev, i) => {
        const isTransition = ev.event_type === "state_transition";
        const badge = STATE_BADGE_STYLE[ev.state] ?? { bg: "bg-[var(--bg-raised)]", text: "text-[var(--text-secondary)]" };

        if (isTransition) {
          return (
            <div key={i} className="mt-4 mb-1">
              {/* Section divider */}
              <div className="flex items-center gap-2">
                <div className="flex-1 h-px" style={{ background: "var(--border-subtle)" }} />
                <span
                  className={`px-2 py-0.5 text-[10px] font-bold tracking-widest uppercase rounded-sm ${badge.bg} ${badge.text}`}
                >
                  {ev.state}
                </span>
                <div className="flex-1 h-px" style={{ background: "var(--border-subtle)" }} />
              </div>
              {/* Transition message */}
              <div className="mt-1 pl-1 flex items-start gap-2">
                <span className="shrink-0 w-16" style={{ color: "var(--text-dim)" }}>
                  {formatTime(ev.timestamp)}
                </span>
                <span style={{ color: "var(--text-secondary)" }}>{ev.message}</span>
              </div>
            </div>
          );
        }

        // Message color by event type — three-color system
        const msgColor =
          ev.event_type === "validation_result"
            ? ev.data?.passed
              ? "var(--c-green)"
              : "var(--c-red)"
            : ev.event_type === "error"
            ? "var(--c-red)"
            : ev.event_type === "patch_generated"
            ? "var(--c-amber)"
            : ev.event_type === "suspect_ranking"
            ? "var(--text-primary)"
            : ev.event_type === "best_effort_report"
            ? "var(--c-red)"
            : "var(--text-secondary)";

        const sigil = EVENT_SIGIL[ev.event_type] ?? " ·";
        const sigilColor = msgColor;

        return (
          <div
            key={i}
            className="flex items-start gap-2 py-0.5 pl-1 rounded"
            style={{ ["--hover-bg" as string]: "var(--bg-raised)" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-raised)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "")}
          >
            <span className="shrink-0 w-16" style={{ color: "var(--text-dim)" }}>
              {formatTime(ev.timestamp)}
            </span>
            <span className="shrink-0 w-4 text-right" style={{ color: sigilColor }}>
              {sigil}
            </span>
            <span style={{ color: msgColor }}>{ev.message}</span>
          </div>
        );
      })}

      <div ref={bottomRef} />
    </div>
  );
}
