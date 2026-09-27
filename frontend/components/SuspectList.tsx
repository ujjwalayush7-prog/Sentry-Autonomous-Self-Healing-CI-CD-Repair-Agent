"use client";

import { useState } from "react";
import { SuspectFile } from "@/lib/types";
import { ChevronDown, ChevronRight } from "lucide-react";

interface SuspectListProps {
  suspects: SuspectFile[];
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  // Three-color system: high → red (it's a suspect, high confidence = worrying),
  // medium → amber, low → dim
  const barColor =
    pct >= 70
      ? "background: var(--c-red)"
      : pct >= 40
      ? "background: var(--c-amber)"
      : "background: var(--border-active)";

  return (
    <div className="flex items-center gap-2 shrink-0">
      <div
        className="w-20 h-1 rounded-full overflow-hidden"
        style={{ background: "var(--border-subtle)" }}
      >
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, [barColor.split(":")[0].trim()]: barColor.split(":")[1].trim() }}
        />
      </div>
      <span className="text-[11px] font-mono w-8 text-right" style={{ color: "var(--text-secondary)" }}>
        {pct}%
      </span>
    </div>
  );
}

export default function SuspectList({ suspects }: SuspectListProps) {
  const [expanded, setExpanded] = useState<number | null>(0);

  if (!suspects || suspects.length === 0) return null;

  return (
    <div className="space-y-1">
      {suspects.map((s) => {
        const isOpen = expanded === s.rank;
        return (
          <div
            key={s.rank}
            className="overflow-hidden rounded"
            style={{ border: "1px solid var(--border-subtle)" }}
          >
            <button
              onClick={() => setExpanded(isOpen ? null : s.rank)}
              className="w-full flex items-center gap-2 px-3 py-2 text-left transition-colors"
              style={{ background: "var(--bg-raised)" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--border-subtle)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "var(--bg-raised)")}
            >
              <span className="text-[11px] font-mono w-5 shrink-0" style={{ color: "var(--text-dim)" }}>
                #{s.rank}
              </span>
              <span className="flex-1 text-sm font-mono truncate" style={{ color: "var(--text-primary)" }}>
                {s.file_path}
              </span>
              <ConfidenceBar value={s.confidence} />
              {isOpen ? (
                <ChevronDown className="w-3 h-3 shrink-0" style={{ color: "var(--text-secondary)" }} />
              ) : (
                <ChevronRight className="w-3 h-3 shrink-0" style={{ color: "var(--text-secondary)" }} />
              )}
            </button>

            {isOpen && (
              <div
                className="px-3 py-3 space-y-3 text-xs"
                style={{ background: "var(--bg-surface)" }}
              >
                <div>
                  <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: "var(--text-dim)" }}>
                    Reasoning
                  </div>
                  <p style={{ color: "var(--text-secondary)" }}>{s.reasoning}</p>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: "var(--text-dim)" }}>
                    Suspected defect
                  </div>
                  <p style={{ color: "var(--c-amber)" }}>{s.suspected_defect}</p>
                </div>
                {s.relevant_lines && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: "var(--text-dim)" }}>
                      Relevant lines
                    </div>
                    <p className="font-mono" style={{ color: "var(--text-secondary)" }}>{s.relevant_lines}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
