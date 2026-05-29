import type { AgentRun } from "../types/domain";
import { formatApiDateTimeLocal } from "../utils/apiTime";

/** User-facing run label (internal run id stays in URLs only). */
export function runDisplayLabel(run: Pick<AgentRun, "session_id" | "attempt_index" | "started_at">): string {
  const attempt = run.attempt_index ?? 1;
  const session = run.session_id?.trim();
  if (session) {
    return `会话 ${session} · 第 ${attempt} 次`;
  }
  return `第 ${attempt} 次 · ${formatApiDateTimeLocal(run.started_at)}`;
}
