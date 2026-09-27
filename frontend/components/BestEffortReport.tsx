"use client";

import { useState } from "react";
import { BestEffortReportData, AttemptRecord } from "@/lib/types";
import { AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";

interface BestEffortReportProps {
  report: BestEffortReportData;
}

function AttemptRow({ record }: { record: AttemptRecord }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-slate-700 rounded overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 px-3 py-2 bg-slate-800 hover:bg-slate-700 transition-colors text-left"
      >
        <span className="text-xs font-mono text-slate-400">Attempt {record.attempt}</span>
        <span className="text-xs font-mono text-slate-500 flex-1 truncate">{record.target_file}</span>
        <span
          className={`text-xs font-semibold ${
            record.validation_passed ? "text-green-400" : "text-red-400"
          }`}
        >
          {record.validation_passed ? "PASS" : "FAIL"}
        </span>
        <span className="text-xs text-slate-500">
          {record.tests_passed}/{record.tests_total}
        </span>
        {open ? (
          <ChevronDown className="w-3 h-3 text-slate-500 shrink-0" />
        ) : (
          <ChevronRight className="w-3 h-3 text-slate-500 shrink-0" />
        )}
      </button>
      {open && (
        <div className="px-3 py-2 bg-slate-900 space-y-2 text-xs">
          <div>
            <span className="text-slate-500 uppercase tracking-wide text-[10px]">Explanation</span>
            <p className="text-slate-300 mt-0.5">{record.explanation}</p>
          </div>
          {record.stack_trace && (
            <div>
              <span className="text-slate-500 uppercase tracking-wide text-[10px]">Stack trace</span>
              <pre className="mt-0.5 text-red-300 bg-slate-950 rounded p-2 overflow-x-auto whitespace-pre-wrap text-[11px]">
                {record.stack_trace}
              </pre>
            </div>
          )}
          <div>
            <span className="text-slate-500 uppercase tracking-wide text-[10px]">Diff (failed)</span>
            <pre className="mt-0.5 text-slate-400 bg-slate-950 rounded p-2 overflow-x-auto text-[11px] whitespace-pre">
              {record.unified_diff}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

export default function BestEffortReport({ report }: BestEffortReportProps) {
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start gap-2 bg-red-950 border border-red-700 rounded-lg p-3">
        <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
        <div>
          <div className="text-sm font-semibold text-red-300">
            {report.status.replace(/_/g, " ")}
          </div>
          <div className="text-xs text-red-400 mt-0.5">
            {report.attempts_exhausted} attempt{report.attempts_exhausted !== 1 ? "s" : ""} exhausted — bug unresolved
          </div>
        </div>
      </div>

      {/* Best hypothesis */}
      <div>
        <div className="text-xs text-slate-500 uppercase tracking-wide mb-1">Best hypothesis</div>
        <p className="text-sm text-slate-300 bg-slate-900 rounded p-3 border border-slate-700">
          {report.best_hypothesis}
        </p>
      </div>

      {/* Top suspects */}
      {report.top_suspects.length > 0 && (
        <div>
          <div className="text-xs text-slate-500 uppercase tracking-wide mb-1">Top suspects</div>
          <div className="space-y-1">
            {report.top_suspects.map((s) => (
              <div
                key={s.rank}
                className="flex items-center gap-2 bg-slate-900 border border-slate-700 rounded px-3 py-2 text-xs"
              >
                <span className="text-slate-500 font-mono w-4">#{s.rank}</span>
                <span className="font-mono text-orange-300 flex-1">{s.file_path}</span>
                <span className="text-slate-500">{Math.round(s.confidence * 100)}% confidence</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Attempt history */}
      {report.attempt_history.length > 0 && (
        <div>
          <div className="text-xs text-slate-500 uppercase tracking-wide mb-1">Attempt history</div>
          <div className="space-y-1">
            {report.attempt_history.map((rec) => (
              <AttemptRow key={rec.attempt} record={rec} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
