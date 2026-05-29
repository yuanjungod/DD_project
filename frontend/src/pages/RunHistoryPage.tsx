import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { listEngagements, listRuns } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import { ENGAGEMENT_LABELS } from "../domain/engagementLabels";
import { engagementIdentityLabel } from "../domain/engagementIdentity";
import { runDisplayLabel } from "../domain/runDisplay";
import { resolveRunStatus, runStatusLabel, runStatusClassName } from "../domain/runStatus";
import type { Engagement } from "../types/domain";
import type { AgentRun } from "../types/domain";
import { formatApiDateTimeLocal } from "../utils/apiTime";

export function RunHistoryPage() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [error, setError] = useState("");

  const engagementLabelById = useMemo(() => {
    return new Map(engagements.map((engagement) => [engagement.id, engagementIdentityLabel(engagement)]));
  }, [engagements]);

  useEffect(() => {
    Promise.all([listRuns(), listEngagements()])
      .then(([runItems, engagementItems]) => {
        setRuns(runItems);
        setEngagements(engagementItems);
      })
      .catch((err: unknown) => setError(String(err)));
  }, []);

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Audit Trail</p>
        <h1>跑的历史记录</h1>
        <p>集中查看所有可访问任务的运行记录、状态与步骤数量。</p>
      </header>
      {error ? <div className="error">{error}</div> : null}
      <SectionCard title="Run 历史">
        <div className="history-table" role="table" aria-label="Run 历史">
          <div className="history-table__row history-table__row--head" role="row">
            <span role="columnheader">Run</span>
            <span role="columnheader">{ENGAGEMENT_LABELS.entity}</span>
            <span role="columnheader">状态</span>
            <span role="columnheader">步骤</span>
            <span role="columnheader">时间</span>
          </div>
          {runs.length === 0 ? (
            <p className="muted history-table__empty">暂无 Run 记录。</p>
          ) : (
            runs.map((run) => {
              const status = resolveRunStatus(run);
              return (
              <div key={run.id} className="history-table__row" role="row">
                <Link to={`/engagements/${encodeURIComponent(run.engagement_id)}/outputs`} role="cell">
                  {runDisplayLabel(run)}
                </Link>
                <Link to={`/engagements/${encodeURIComponent(run.engagement_id)}/outputs`} role="cell">
                  {engagementLabelById.get(run.engagement_id) ?? ENGAGEMENT_LABELS.entity}
                </Link>
                <span className={`status ${runStatusClassName(run)}`} role="cell">
                  {runStatusLabel(status)}
                </span>
                <span role="cell">{run.steps.length}</span>
                <span role="cell">{formatApiDateTimeLocal(run.started_at)}</span>
              </div>
              );
            })
          )}
        </div>
      </SectionCard>
    </div>
  );
}
