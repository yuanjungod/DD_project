import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { createResource, getRun, listEvidence, listProjectRuns, listProjects, listReports, listResources, startRun } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import { workflowName } from "../data/workflows";
import type { AgentRun, Evidence, Project, Report, Resource } from "../types/domain";

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
  const [loading, setLoading] = useState(false);

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
    if (!projectId) return;
    refresh().catch((err: unknown) => setError(String(err)));
  }, [projectId]);

  async function handleAddResource() {
    if (!resourceValue.trim()) return;
    setLoading(true);
    setError("");
    try {
      await createResource(projectId, { type: "trusted_source", value: resourceValue });
      setResourceValue("");
      await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleStartRun() {
    setLoading(true);
    setError("");
    try {
      const started = await startRun(projectId);
      const latest = await getRun(started.id);
      setActiveRun(latest);
      await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

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
        <button onClick={handleStartRun} disabled={loading}>
          {loading ? "执行中..." : "启动尽调 Run"}
        </button>
      </header>
      {error ? <div className="error">{error}</div> : null}
      <div className="grid two">
        <SectionCard title="应用资源" description="给当前公司应用补充可信来源、文件 ID 或外部线索。">
          <div className="inline-form">
            <input value={resourceValue} onChange={(event) => setResourceValue(event.target.value)} />
            <button onClick={handleAddResource} disabled={loading}>
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
                <p>{new Date(run.started_at).toLocaleString()}</p>
              </li>
            ))}
          </ul>
        </SectionCard>
      </div>
      <div className="grid three">
        <SectionCard title="Agent 执行状态">
          {activeRun?.steps.length ? (
            <ol className="timeline">
              {activeRun.steps.map((step) => (
                <li key={step.id}>
                  <span className={`status ${step.status}`}>{step.status}</span>
                  <strong>{step.agent}</strong>
                  <p>{step.summary}</p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="muted">启动 run 后展示各 agent 状态。</p>
          )}
        </SectionCard>
        <SectionCard title="证据库">
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
          {reports[0] ? (
            <article className="report">
              <h3>{reports[0].title}</h3>
              <span className={`risk ${reports[0].overall_risk}`}>整体风险：{reports[0].overall_risk}</span>
              <p>{reports[0].executive_summary}</p>
            </article>
          ) : (
            <p className="muted">完成 run 后生成报告。</p>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
