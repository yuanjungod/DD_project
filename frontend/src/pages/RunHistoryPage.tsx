import { Fragment, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listRuns } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import type { AgentRun } from "../types/domain";

export function RunHistoryPage() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    listRuns()
      .then(setRuns)
      .catch((err: unknown) => setError(String(err)));
  }, []);

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Audit Trail</p>
        <h1>跑的历史记录</h1>
        <p>集中查看所有可访问项目的 Agent run、状态、证据数量和报告结果。</p>
      </header>
      {error ? <div className="error">{error}</div> : null}
      <SectionCard title="Run 历史">
        <div className="history-table">
          <span>Run</span>
          <span>项目</span>
          <span>状态</span>
          <span>Agent</span>
          <span>证据</span>
          <span>时间</span>
          {runs.map((run) => (
            <Fragment key={run.id}>
              <Link to={`/projects/${run.project_id}`}>
                {run.id}
              </Link>
              <span>{run.project_id}</span>
              <span className={`status ${run.status}`}>
                {run.status}
              </span>
              <span>{run.steps.length}</span>
              <span>{run.evidence.length}</span>
              <span>{new Date(run.started_at).toLocaleString()}</span>
            </Fragment>
          ))}
        </div>
      </SectionCard>
    </div>
  );
}
