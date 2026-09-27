"use client";

import dynamic from "next/dynamic";

// react-diff-viewer-continued uses browser APIs — must be client-only
const ReactDiffViewer = dynamic(() => import("react-diff-viewer-continued"), {
  ssr: false,
  loading: () => (
    <div className="p-3 text-xs font-mono" style={{ color: "var(--text-dim)" }}>
      Loading diff viewer…
    </div>
  ),
});

interface DiffViewerProps {
  diff: string;
  filename: string;
  attempt: number;
}

/**
 * Parses a unified diff string into separate oldValue / newValue strings
 * suitable for react-diff-viewer-continued.
 *
 * Strategy: walk hunk lines.
 *   Lines starting with '-' (but not '---') → old content (strip '-' prefix)
 *   Lines starting with '+' (but not '+++') → new content (strip '+' prefix)
 *   Context lines (no prefix / ' ' prefix)  → both old and new
 */
function parseDiff(unified: string): { oldValue: string; newValue: string } {
  const lines = unified.split("\n");
  const oldLines: string[] = [];
  const newLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith("diff ") || line.startsWith("index ") || line.startsWith("@@")) continue;
    if (line.startsWith("--- ") || line.startsWith("+++ ")) continue;
    if (line.startsWith("-")) {
      oldLines.push(line.slice(1));
    } else if (line.startsWith("+")) {
      newLines.push(line.slice(1));
    } else {
      const content = line.startsWith(" ") ? line.slice(1) : line;
      oldLines.push(content);
      newLines.push(content);
    }
  }

  return { oldValue: oldLines.join("\n"), newValue: newLines.join("\n") };
}

export default function DiffViewer({ diff, filename, attempt }: DiffViewerProps) {
  if (!diff) return null;
  const { oldValue, newValue } = parseDiff(diff);

  return (
    <div
      className="overflow-hidden"
      style={{ borderRadius: "6px", border: "1px solid var(--border-subtle)" }}
    >
      {/* Header — mono font, matches log header style */}
      <div
        className="flex items-center justify-between px-3 py-2 font-mono text-xs"
        style={{
          background: "var(--bg-raised)",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        <span style={{ color: "var(--text-primary)" }}>{filename}</span>
        <span style={{ color: "var(--text-secondary)" }}>attempt {attempt}</span>
      </div>

      {/* Diff body — force dark theme via CSS overrides */}
      <div
        className="text-xs font-mono"
        style={{
          /* Ensure the diff library's table fills the token background */
          ["--rdv-bg" as string]: "var(--bg-surface)",
        }}
      >
        {/* Scoped overrides for react-diff-viewer-continued internals */}
        <style>{`
          .rdv-wrap pre, .rdv-wrap table, .rdv-wrap td, .rdv-wrap tr {
            background-color: var(--bg-surface) !important;
            color: var(--text-primary) !important;
            font-family: var(--font-mono) !important;
            font-size: 12px !important;
          }
          .rdv-wrap .diff-removed, .rdv-wrap .diff-removed td {
            background-color: var(--c-red-bg) !important;
          }
          .rdv-wrap .diff-removed .diff-removed-gutter,
          .rdv-wrap .diff-removed .diff-code-remove {
            background-color: rgba(192, 82, 74, 0.18) !important;
          }
          .rdv-wrap .diff-added, .rdv-wrap .diff-added td {
            background-color: var(--c-green-bg) !important;
          }
          .rdv-wrap .diff-added .diff-added-gutter,
          .rdv-wrap .diff-added .diff-code-add {
            background-color: rgba(61, 207, 110, 0.12) !important;
          }
          .rdv-wrap .line-number, .rdv-wrap .diff-marker {
            color: var(--text-dim) !important;
            background-color: var(--bg-raised) !important;
          }
        `}</style>
        <div className="rdv-wrap">
          <ReactDiffViewer
            oldValue={oldValue}
            newValue={newValue}
            splitView={false}
            useDarkTheme={true}
            hideLineNumbers={false}
            showDiffOnly={true}
          />
        </div>
      </div>
    </div>
  );
}
