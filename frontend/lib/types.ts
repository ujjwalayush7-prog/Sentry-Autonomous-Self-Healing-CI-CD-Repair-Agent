/**
 * Canonical TypeScript types matching the backend orchestrator event protocol.
 * Source of truth: backend/orchestrator/events.py
 */

// ---------------------------------------------------------------------------
// Enums (string unions mirror the Python Enum values)
// ---------------------------------------------------------------------------

export type AgentState =
  | "INGEST"
  | "REPRODUCE"
  | "NAVIGATE"
  | "HYPOTHESIZE"
  | "PATCH"
  | "VALIDATE"
  | "PR_CREATE"
  | "REPORT_BEST_EFFORT"
  | "DONE"
  | "ERROR";

export type EventType =
  | "state_transition"
  | "reasoning_step"
  | "suspect_ranking"
  | "patch_generated"
  | "validation_result"
  | "pr_created"
  | "best_effort_report"
  | "error"
  | "log"
  | "done"; // terminal sentinel sent by backend/main.py

// Ordered pipeline states for the timeline (terminal states excluded)
export const PIPELINE_STATES: AgentState[] = [
  "INGEST",
  "REPRODUCE",
  "NAVIGATE",
  "HYPOTHESIZE",
  "PATCH",
  "VALIDATE",
  "PR_CREATE",
  "REPORT_BEST_EFFORT",
];

// ---------------------------------------------------------------------------
// Event data payloads (typed per event_type)
// ---------------------------------------------------------------------------

export interface StateTransitionData {
  from_state: string;
  to_state: string;
}

export interface ReasoningStepData {
  step_number: number;
  description: string;
  // Optional extras that appear in specific states:
  repo_url?: string;
  commit_sha?: string | null;
  before_counts?: TestCounts;
  after_counts?: TestCounts;
  stack_trace?: string;
  sandbox_type?: string;
  file_tree_preview?: string;
  referenced_files?: string[];
  files_loaded?: string[];
  model_id?: string;
  hypothesis?: string;
  files_loaded_for_patch?: string[];
  applied?: boolean;
  explanation?: string;
  top_suspect?: SuspectFile;
}

export interface SuspectFile {
  rank: number;
  file_path: string;
  confidence: number;
  reasoning: string;
  suspected_defect: string;
  relevant_lines?: string | null;
}

export interface SuspectRankingData {
  suspects: SuspectFile[];
  reasoning_trace: string;
  files_analyzed: number;
  model_id: string;
}

export interface PatchGeneratedData {
  target_file: string;
  unified_diff: string;
  explanation: string;
  attempt: number;
  model_id: string;
}

export interface ValidationResultData {
  passed: boolean;
  tests_passed: number;
  tests_failed: number;
  tests_total: number;
  attempt: number;
  stdout_summary: string;
}

export interface TestCounts {
  tests_total: number;
  tests_passed: number;
  tests_failed: number;
}

export interface AttemptRecord {
  attempt: number;
  target_file: string;
  unified_diff: string;
  explanation: string;
  patch_applied: boolean;
  validation_passed: boolean;
  tests_total: number;
  tests_passed: number;
  tests_failed: number;
  stack_trace: string;
}

export interface BestEffortReportData {
  status: string;
  attempts_exhausted: number;
  best_hypothesis: string;
  top_suspects: SuspectFile[];
  attempt_history: AttemptRecord[];
}

// ---------------------------------------------------------------------------
// Canonical event envelope
// ---------------------------------------------------------------------------

export interface OrchestratorEvent {
  event_type: EventType;
  state: AgentState;
  timestamp: string;
  message: string;
  // data shape depends on event_type; we use a union-friendly record here
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: Record<string, any>;
}

// ---------------------------------------------------------------------------
// Full run result (mirrors OrchestratorRunResult in state_machine.py)
// ---------------------------------------------------------------------------

export interface RunResult {
  fixed: boolean;
  final_state: string;
  repo_url: string;
  runtime: string;
  test_cmd: string;
  model_id: string;
  attempts_used: number;
  max_attempts: number;
  before_counts: TestCounts;
  after_counts: TestCounts;
  initial_stack_trace: string;
  suspects: SuspectFile[];
  root_cause_hypothesis: string;
  final_diff: string;
  final_explanation: string;
  target_file: string;
  attempt_history: AttemptRecord[];
  events: OrchestratorEvent[];
  duration_seconds: number;
  pr_url: string | null;
  best_effort_report: BestEffortReportData | null;
}
