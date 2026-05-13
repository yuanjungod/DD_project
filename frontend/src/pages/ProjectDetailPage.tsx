import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import {
  createResource,
  getRun,
  listEvidence,
  listProjectRuns,
  listProjects,
  listReports,
  listResources,
  startRun,
} from "../api/client";
import { SectionCard } from "../components/SectionCard";
import { workflowName } from "../data/workflows";
import type { AgentRun, Evidence, Project, Report, Resource } from "../types/domain";
import { formatApiDateTimeLocal } from "../utils/apiTime";

export function ProjectDetailPage() {
  const { projectId = "" } = useParams();
  const [project, setProject] = useState<Project | null>(null);
  const [resources, setResources] = useState<Resource[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [activeRun, setActiveRun] = useState<AgentRun | null>(null);
  const [resourceValue, setResourceValue] = useState("公司官网");
  const [error, setError] = useState("");
  const [resourceLoading, setResourceLoading] = useState(false);
  const [runStarting, setRunStarting] = useState(false);
  const [pollingRunId, setPollingRunId] = useState<string | null>(null);

  async function refresh() {
    const [projects, resourceItems, evidenceItems, reportItems, runItems] = await Promise.all([
      listProjects(),
      listResources(projectId),
      listEvidence(projectId),
      listReports(projectId),
      listProjectRuns(projectId),
    ]);
    setProject(projects.find((item) => item.id === projectId) ?? null);
    setResources(resourceItems);
    setEvidence(evidenceItems);
    setReports(reportItems);
    setRuns(runItems);
    setActiveRun(runItems[0] ?? null);
  }

  useEffect(() => {
    setPollingRunId(null);
    setRunStarting(false);
  }, [projectId]);

  useEffect(() => {
    if (!projectId) return;
    refresh().catch((err: unknown) => setError(String(err)));
  }, [projectId]);

  useEffect(() => {
    if (!pollingRunId) return;
    const id = pollingRunId;

    async function tick() {
      try {
        const latest = await getRun(id);
        setActiveRun(latest);
        const [runItems, evidenceItems] = await Promise.all([listProjectRuns(projectId), listEvidence(projectId)]);
        setRuns(runItems);
        setEvidence(evidenceItems);
        if (latest.status === "completed" || latest.status === "failed") {
          setPollingRunId(null);
          setRunStarting(false);
          await refresh();
        }
      } catch (err: unknown) {
        setPollingRunId(null);
        setRunStarting(false);
        setError(String(err));
      }
    }

    void tick();
    const interval = window.setInterval(() => void tick(), 2000);
    return () => window.clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh intentionally stable per navigation (projectId)
  }, [pollingRunId, projectId]);

  async function handleAddResource() {
    if (!resourceValue.trim()) return;
    setResourceLoading(true);
    setError("");
    try {
      await createResource(projectId, { type: "trusted_source", value: resourceValue });
      setResourceValue("");
      await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setResourceLoading(false);
    }
  }

  async function handleStartRun() {
    setRunStarting(true);
    setError("");
    try {
      const started = await startRun(projectId);
      setActiveRun(started);
      await refresh();
      if (started.status === "running" || started.status === "pending") {
        setPollingRunId(started.id);
      } else {
        setRunStarting(false);
      }
    } catch (err) {
      setError(String(err));
      setRunStarting(false);
    }
  }

  const runErr =
    typeof activeRun?.raw_result === "object" && activeRun?.raw_result !== null && "error" in activeRun.raw_result
      ? String((activeRun.raw_result as { error?: string }).error ?? "")
      : "";

  const runInFlight = Boolean(pollingRunId) || activeRun?.status === "running" || runStarting;
  const orderedSteps = [...(activeRun?.steps ?? [])].sort((a, b) => a.id.localeCompare(b.id));

  return (
    <div className="page-stack">
      <header className="page-hero action-hero">
        <div>
          <p className="eyebrow">Application Detail</p>
          <h1>{project?.company_config.target_company.name ?? "尽调应用"}</h1>
          <p>
            {project
              ? `${workflowName(project.company_config.scope.workflow_template_id ?? project.company_config.scope.workflow_id)} · v${
                  project.company_config.scope.workflow_template_version ?? 1
                }`
              : "加载中"}
          </p>
        </div>
        <button onClick={handleStartRun} disabled={runStarting}>
          {runStarting ? "执行中…" : "启动尽调 Run"}
        </button>
      </header>
      {error ? <div className="error">{error}</div> : null}
      <div className="grid two">
        <SectionCard title="应用资源" description="给当前公司应用补充可信来源、文件 ID 或外部线索。">
          <div className="inline-form">
            <input value={resourceValue} onChange={(event) => setResourceValue(event.target.value)} />
            <button onClick={handleAddResource} disabled={resourceLoading}>
              添加资源
            </button>
          </div>
          <ul className="list">
            {resources.map((resource) => (
              <li key={resource.id}>
                <span>{resource.type}</span>
                <strong>{resource.value}</strong>
              </li>
            ))}
          </ul>
        </SectionCard>
        <SectionCard title="本应用历史 Run">
          <ul className="list">
            {runs.map((run) => (
              <li key={run.id}>
                <span>{run.status}</span>
                <strong>{run.id}</strong>
                <p>{formatApiDateTimeLocal(run.started_at)}</p>
              </li>
            ))}
          </ul>
          {runs.length === 0 && !runStarting ? (
            <p className="muted">尚无 Run。点击右上角启动后即可在此看到记录。</p>
          ) : null}
        </SectionCard>
      </div>
      <div className="grid three">
        <SectionCard title="Agent 执行状态">
          {activeRun?.status === "failed" ? <p className="error">{runErr || "Run 失败"}</p> : null}
          {orderedSteps.length ? (
            <ol className="timeline">
              {orderedSteps.map((step) => (
                <li key={step.id}>
                  <span className={`status ${step.status}`}>{step.status}</span>
                  <strong>{step.agent}</strong>
                  <p>{step.summary || (step.status === "running" ? "执行中…" : "")}</p>
                </li>
              ))}
            </ol>
          ) : runInFlight ? (
            <p className="muted">
              后台正在执行尽调链路。若 Agent 服务配置了 <code>PLATFORM_CALLBACK_BASE_URL</code> 指向本后端，步骤会逐步出现；否则需待全流程结束。
            </p>
          ) : (
            <p className="muted">启动 run 后展示各 agent 状态。</p>
          )}
          {runInFlight && orderedSteps.length ? (
            <p className="muted" style={{ marginTop: "0.75rem" }}>
              流程进行中；步骤与证据会随回调或轮询持续刷新。
            </p>
          ) : null}
        </SectionCard>
        <SectionCard title="证据库">
          {runInFlight && evidence.length === 0 ? (
            <p className="muted">证据会随各 Agent 回调写入；若未配置回调，将在 Run 结束后一次性展示。</p>
          ) : null}
          <ul className="list evidence-list">
            {evidence.map((item) => (
              <li key={item.id}>
                <span>{item.collected_by}</span>
                <strong>{item.title}</strong>
                <p>{item.excerpt}</p>
              </li>
            ))}
          </ul>
        </SectionCard>
        <SectionCard title="尽调报告">
          {runInFlight && !reports[0] ? (
            <p className="muted">报告在 Run 成功完成后写入；请稍候或留意上方 Run 状态。</p>
          ) : null}
          {reports[0] ? (
            <article className="report">
              <h3>{reports[0].title}</h3>
              <span className={`risk ${reports[0].overall_risk}`}>整体风险：{reports[0].overall_risk}</span>
              <p>{reports[0].executive_summary}</p>
            </article>
          ) : !runInFlight ? (
            <p className="muted">完成 run 后生成报告。</p>
          ) : null}
        </SectionCard>
      </div>
    </div>
  );
}
