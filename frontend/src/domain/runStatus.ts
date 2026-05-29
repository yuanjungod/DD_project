import type { AgentRun, AgentStep } from "../types/domain";

export const RUN_STATUS_LABELS: Record<string, string> = {
  completed: "已完成",
  failed: "失败",
  paused: "待复核",
  pending: "排队中",
  running: "运行中",
};

export function runStatusLabel(status?: string | null): string {
  if (!status) return "暂无";
  return RUN_STATUS_LABELS[status] ?? status;
}

const STALE_RUNNING_MS = 30 * 60 * 1000;

function stepStatuses(steps: AgentStep[]): string[] {
  return steps.map((step) => step.status).filter(Boolean);
}

/** Mirror backend run status resolution for immediate UI consistency. */
export function resolveRunStatus(run: Pick<AgentRun, "status" | "steps" | "started_at" | "raw_result">): string {
  const stored = run.status?.trim() || "pending";
  if (stored === "completed" || stored === "failed" || stored === "paused") {
    return stored;
  }

  const raw = run.raw_result;
  if (raw && typeof raw === "object" && raw.error != null && String(raw.error).trim()) {
    return "failed";
  }

  const statuses = stepStatuses(run.steps ?? []);
  if (statuses.length > 0) {
    if (statuses.some((status) => status === "failed")) return "failed";
    if (statuses.some((status) => status === "running")) return "running";
    if (statuses.every((status) => status === "completed")) return "completed";
  }

  if (stored === "running") {
    const started = Date.parse(run.started_at);
    if (Number.isFinite(started) && Date.now() - started > STALE_RUNNING_MS && statuses.length === 0) {
      return "failed";
    }
  }

  return stored;
}

export function runStatusClassName(run: Pick<AgentRun, "status" | "steps" | "started_at" | "raw_result">): string {
  return resolveRunStatus(run);
}
