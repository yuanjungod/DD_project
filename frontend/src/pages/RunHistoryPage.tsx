import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { deleteEngagementRuns, deleteWorkflowRuns, listEngagements, listRuns, listWorkflowTemplates } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import { ENGAGEMENT_LABELS } from "../domain/engagementLabels";
import { engagementIdentityLabel } from "../domain/engagementIdentity";
import { runDisplayLabel } from "../domain/runDisplay";
import { resolveRunStatus, runStatusLabel, runStatusClassName } from "../domain/runStatus";
import type { Engagement } from "../types/domain";
import type { AgentRun } from "../types/domain";
import type { WorkflowTemplate } from "../types/domain";
import { formatApiDateTimeLocal } from "../utils/apiTime";

export function RunHistoryPage() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowTemplate[]>([]);
  const [selectedEngagementId, setSelectedEngagementId] = useState("");
  const [selectedWorkflowId, setSelectedWorkflowId] = useState("");
  const [busyAction, setBusyAction] = useState<"engagement" | "workflow" | "">("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const engagementLabelById = useMemo(() => {
    return new Map(engagements.map((engagement) => [engagement.id, engagementIdentityLabel(engagement)]));
  }, [engagements]);

  const workflowNameById = useMemo(() => {
    return new Map(workflows.map((workflow) => [workflow.id, workflow.name]));
  }, [workflows]);

  const workflowChoices = useMemo(() => {
    const unique = new Set<string>();
    for (const engagement of engagements) {
      const wf = String(engagement.instance_config?.workflow_template_id || "").trim();
      if (wf) unique.add(wf);
    }
    return Array.from(unique.values());
  }, [engagements]);

  async function refresh() {
    const [runItems, engagementItems, workflowItems] = await Promise.all([
      listRuns(),
      listEngagements(),
      listWorkflowTemplates(),
    ]);
    setRuns(runItems);
    setEngagements(engagementItems);
    setWorkflows(workflowItems);
    setSelectedEngagementId((prev) => (prev && engagementItems.some((item) => item.id === prev) ? prev : engagementItems[0]?.id ?? ""));
    setSelectedWorkflowId((prev) => {
      const options = new Set(
        engagementItems
          .map((item) => String(item.instance_config?.workflow_template_id || "").trim())
          .filter(Boolean),
      );
      if (prev && options.has(prev)) return prev;
      return Array.from(options.values())[0] ?? "";
    });
  }

  useEffect(() => {
    refresh().catch((err: unknown) => setError(String(err)));
  }, []);

  async function handleDeleteEngagementRuns() {
    if (!selectedEngagementId) {
      setError("请先选择任务。");
      return;
    }
    const label = engagementLabelById.get(selectedEngagementId) ?? ENGAGEMENT_LABELS.entity;
    const ok = window.confirm(`删除「${label}」的全部运行记录？此操作不可恢复。`);
    if (!ok) return;
    setBusyAction("engagement");
    setError("");
    setNotice("");
    try {
      const result = await deleteEngagementRuns(selectedEngagementId);
      setNotice(`已删除 ${result.deleted_runs} 条运行记录（清理会话 ${result.deleted_sessions} 条）。`);
      await refresh();
    } catch (err: unknown) {
      setError(String(err));
    } finally {
      setBusyAction("");
    }
  }

  async function handleDeleteWorkflowRuns() {
    if (!selectedWorkflowId) {
      setError("请先选择 Workflow 模板。");
      return;
    }
    const workflowName = workflowNameById.get(selectedWorkflowId) ?? selectedWorkflowId;
    const ok = window.confirm(`删除模板「${workflowName}」关联的全部运行记录？此操作不可恢复。`);
    if (!ok) return;
    setBusyAction("workflow");
    setError("");
    setNotice("");
    try {
      const result = await deleteWorkflowRuns(selectedWorkflowId);
      setNotice(
        `已删除 ${result.deleted_runs} 条运行记录，覆盖 ${result.matched_engagements} 个任务（清理会话 ${result.deleted_sessions} 条）。`,
      );
      await refresh();
    } catch (err: unknown) {
      setError(String(err));
    } finally {
      setBusyAction("");
    }
  }

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Audit Trail</p>
        <h1>跑的历史记录</h1>
        <p>集中查看所有可访问任务的运行记录、状态与步骤数量。</p>
      </header>
      {error ? <div className="error">{error}</div> : null}
      {notice ? <div className="notice">{notice}</div> : null}
      <SectionCard title="批量删除记录" description="支持按任务或按 Workflow 模板批量清理运行历史。">
        <div className="grid two">
          <label>
            按任务删除
            <select value={selectedEngagementId} onChange={(event) => setSelectedEngagementId(event.target.value)}>
              {engagements.map((engagement) => (
                <option key={engagement.id} value={engagement.id}>
                  {engagementIdentityLabel(engagement)}
                </option>
              ))}
            </select>
            <button type="button" className="danger-button" disabled={busyAction !== ""} onClick={() => void handleDeleteEngagementRuns()}>
              {busyAction === "engagement" ? "删除中…" : "删除该任务全部记录"}
            </button>
          </label>
          <label>
            按 Workflow 删除
            <select value={selectedWorkflowId} onChange={(event) => setSelectedWorkflowId(event.target.value)}>
              {workflowChoices.map((workflowId) => (
                <option key={workflowId} value={workflowId}>
                  {workflowNameById.get(workflowId) ?? workflowId}
                </option>
              ))}
            </select>
            <button type="button" className="danger-button" disabled={busyAction !== ""} onClick={() => void handleDeleteWorkflowRuns()}>
              {busyAction === "workflow" ? "删除中…" : "删除该 Workflow 全部记录"}
            </button>
          </label>
        </div>
      </SectionCard>
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
