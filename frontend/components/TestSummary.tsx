"use client";

import { TestCounts } from "@/lib/types";
import { CheckCircle2, XCircle } from "lucide-react";

interface TestSummaryProps {
  before: TestCounts;
  after: TestCounts;
  fixed: boolean;
}

function CountCard({
  label,
  counts,
  highlight,
}: {
  label: string;
  counts: TestCounts;
  highlight: "red" | "green" | "neutral";
}) {
  const borderColor =
    highlight === "green"
      ? "var(--c-green-border)"
      : highlight === "red"
      ? "var(--c-red-border)"
      : "var(--border-subtle)";

  const passColor =
    highlight === "green" ? "var(--c-green)" : "var(--text-primary)";

  const failColor =
    counts.tests_failed > 0 ? "var(--c-red)" : "var(--text-dim)";

  return (
    <div
      className="flex-1 rounded p-4"
      style={{ border: `1px solid ${borderColor}`, background: "var(--bg-surface)" }}
    >
      <div className="text-[10px] uppercase tracking-wider mb-3" style={{ color: "var(--text-dim)" }}>
        {label}
      </div>
      <div className="flex gap-4 items-end">
        <div>
          <div className="text-3xl font-bold font-mono" style={{ color: passColor }}>
            {counts.tests_passed}
          </div>
          <div className="text-[10px] mt-0.5" style={{ color: "var(--text-secondary)" }}>passed</div>
        </div>
        <div className="text-2xl font-mono mb-0.5" style={{ color: "var(--border-active)" }}>/</div>
        <div>
          <div className="text-3xl font-bold font-mono" style={{ color: "var(--text-primary)" }}>
            {counts.tests_total}
          </div>
          <div className="text-[10px] mt-0.5" style={{ color: "var(--text-secondary)" }}>total</div>
        </div>
        {counts.tests_failed > 0 && (
          <div className="ml-auto">
            <div className="text-2xl font-bold font-mono" style={{ color: failColor }}>
              {counts.tests_failed}
            </div>
            <div className="text-[10px] mt-0.5" style={{ color: "var(--text-secondary)" }}>failed</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function TestSummary({ before, after, fixed }: TestSummaryProps) {
  const statusBg    = fixed ? "var(--c-green-bg)"     : "var(--c-red-bg)";
  const statusBorder = fixed ? "var(--c-green-border)" : "var(--c-red-border)";
  const statusColor  = fixed ? "var(--c-green)"        : "var(--c-red)";

  return (
    <div className="space-y-3">
      {/* Status badge */}
      <div
        className="flex items-center gap-2 rounded px-3 py-2 text-sm font-semibold"
        style={{ background: statusBg, border: `1px solid ${statusBorder}`, color: statusColor }}
      >
        {fixed ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
        {fixed ? "RED → GREEN: Bug fixed successfully" : "UNRESOLVED: Max attempts exhausted"}
      </div>

      {/* Before / After cards */}
      <div className="flex gap-2 items-center">
        <CountCard label="Before" counts={before} highlight="red" />
        <div className="text-lg font-mono shrink-0" style={{ color: "var(--border-active)" }}>→</div>
        <CountCard label="After" counts={after} highlight={fixed ? "green" : "red"} />
      </div>
    </div>
  );
}
