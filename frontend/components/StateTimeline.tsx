"use client";

import { AgentState, PIPELINE_STATES } from "@/lib/types";

interface StateTimelineProps {
  currentState: AgentState | null;
  completedStates: AgentState[];
}

const STATE_LABELS: Record<string, string> = {
  INGEST:             "Ingest",
  REPRODUCE:          "Reproduce",
  NAVIGATE:           "Navigate",
  HYPOTHESIZE:        "Hypothesize",
  PATCH:              "Patch",
  VALIDATE:           "Validate",
  PR_CREATE:          "PR Create",
  REPORT_BEST_EFFORT: "Best Effort",
};

type NodeVariant = "done" | "active-amber" | "active-green" | "active-red" | "future";

function getVariant(
  state: AgentState,
  isActive: boolean,
  isDone: boolean
): NodeVariant {
  if (isDone) return "done";
  if (isActive) {
    if (state === "PR_CREATE") return "active-green";
    if (state === "REPORT_BEST_EFFORT") return "active-red";
    return "active-amber";
  }
  return "future";
}

const NODE_STYLES: Record<NodeVariant, {
  outer: string;        // ring + bg of the circle
  inner: string;        // inner dot/icon colour
  label: string;        // label text colour
  pulse: string;        // animation class (from globals.css)
  connectorOut: string; // colour of the line leaving this node
}> = {
  "done": {
    outer:        "border-[var(--border-active)] bg-[var(--bg-raised)]",
    inner:        "text-[var(--c-green)]",
    label:        "text-[var(--text-secondary)]",
    pulse:        "",
    connectorOut: "bg-[var(--border-active)]",
  },
  "active-amber": {
    outer:        "border-[var(--c-amber)] bg-[var(--bg-raised)]",
    inner:        "text-[var(--c-amber)]",
    label:        "text-[var(--text-primary)]",
    pulse:        "timeline-node-active-amber",
    connectorOut: "bg-[var(--border-subtle)]",
  },
  "active-green": {
    outer:        "border-[var(--c-green)] bg-[var(--bg-raised)]",
    inner:        "text-[var(--c-green)]",
    label:        "text-[var(--c-green)]",
    pulse:        "timeline-node-active-green",
    connectorOut: "bg-[var(--border-subtle)]",
  },
  "active-red": {
    outer:        "border-[var(--c-red)] bg-[var(--bg-raised)]",
    inner:        "text-[var(--c-red)]",
    label:        "text-[var(--c-red)]",
    pulse:        "timeline-node-active-red",
    connectorOut: "bg-[var(--border-subtle)]",
  },
  "future": {
    outer:        "border-[var(--border-subtle)] bg-[var(--bg-surface)]",
    inner:        "text-[var(--text-dim)]",
    label:        "text-[var(--text-dim)]",
    pulse:        "",
    connectorOut: "bg-[var(--border-subtle)]",
  },
};

function NodeIcon({ variant }: { variant: NodeVariant }) {
  if (variant === "done") {
    // Checkmark — small, clean
    return (
      <svg viewBox="0 0 12 12" className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="2,6 5,9 10,3" />
      </svg>
    );
  }
  if (variant.startsWith("active")) {
    // Filled inner dot
    return <div className="w-2.5 h-2.5 rounded-full bg-current" />;
  }
  // Future: empty circle rendered by the outer ring itself, inner is invisible
  return <div className="w-2 h-2 rounded-full bg-current opacity-25" />;
}

export default function StateTimeline({ currentState, completedStates }: StateTimelineProps) {
  return (
    <div className="flex flex-wrap items-start gap-y-4">
      {PIPELINE_STATES.map((state, idx) => {
        const isDone   = completedStates.includes(state);
        const isActive = currentState === state;
        const variant  = getVariant(state, isActive, isDone);
        const styles   = NODE_STYLES[variant];
        const isLast   = idx === PIPELINE_STATES.length - 1;

        // Connector brightens when leaving a done node toward an active one
        const nextState = !isLast ? PIPELINE_STATES[idx + 1] : null;
        const nextIsActive = nextState === currentState;
        const connectorCls = isDone && nextIsActive
          ? "bg-[var(--c-amber)]"
          : isDone
          ? "bg-[var(--border-active)]"
          : "bg-[var(--border-subtle)]";

        return (
          <div key={state} className="flex items-center">
            {/* Node + label */}
            <div className="flex flex-col items-center gap-1.5">
              {/* Circle */}
              <div
                className={`
                  w-7 h-7 rounded-full border-2 flex items-center justify-center
                  transition-colors duration-300
                  ${styles.outer} ${styles.pulse}
                `}
              >
                <span className={styles.inner}>
                  <NodeIcon variant={variant} />
                </span>
              </div>
              {/* Label */}
              <span
                className={`
                  text-[10px] font-sans tracking-wide whitespace-nowrap leading-none
                  transition-colors duration-300
                  ${styles.label}
                `}
              >
                {STATE_LABELS[state] ?? state}
              </span>
            </div>

            {/* Connector line — skip after last node */}
            {!isLast && (
              <div
                className={`
                  w-8 h-px mb-[18px] mx-0.5 shrink-0
                  transition-colors duration-500
                  ${connectorCls}
                `}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
