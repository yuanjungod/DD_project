import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  createProject,
  createResource,
  getRun,
  listEvidence,
  listProjects,
  listReports,
  listResources,
  listWorkflowTemplates,
  startRun,
} from "../api/client";
import { SectionCard } from "../components/SectionCard";
import { focusAreasForScenario, workflowName } from "../data/workflows";
import type { AgentRun, CompanyConfig, Evidence, Project, Report, Resource, WorkflowTemplate } from "../types/domain";

const defaultCompanyConfig: CompanyConfig = {
  target_company: {
    name: "Example Robotics",
    aliases: ["ExampleBot"],
    website: "https://example.com",
    jurisdiction: "中国大陆",
    industry: "智能制造",
    keywords: ["仓储自动化", "机器人"],
  },
  scope: {
    workflow_id: "standard_due_diligence",
    workflow_template_id: "standard_due_diligence",
    workflow_template_version: 1,
    scenario: "standard",
    time_range: "近5年",
    focus_areas: focusAreasForScenario("standard"),
    report_language: "zh-CN",
  },
  resources: {
    uploaded_files: [],
    trusted_sources: ["公司官网", "交易所公告", "工商登记信息"],
    blocked_sources: [],
    competitors: ["Peer Robotics", "Warehouse AI"],
  },
};

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function Workbench() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [workflowTemplates, setWorkflowTemplates] = useState<WorkflowTemplate[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [resources, setResources] = useState<Resource[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [run, setRun] = useState<AgentRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [form, setForm] = useState(defaultCompanyConfig);
  const [resourceValue, setResourceValue] = useState("公司官网");

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId),
    [projects, selectedProjectId],
  );

  async function refreshProjects() {
    const [items, workflowItems] = await Promise.all([listProjects(), listWorkflowTemplates()]);
    setProjects(items);
    setWorkflowTemplates(workflowItems);
    if (!selectedProjectId && items[0]) {
      setSelectedProjectId(items[0].id);
    }
  }

  async function refreshProjectData(projectId: string) {
    const [resourceItems, evidenceItems, reportItems] = await Promise.all([
      listResources(projectId),
      listEvidence(projectId),
      listReports(projectId),
    ]);
    setResources(resourceItems);
    setEvidence(evidenceItems);
    setReports(reportItems);
  }

  useEffect(() => {
    refreshProjects().catch((err: unknown) => setError(String(err)));
  }, []);

  useEffect(() => {
    if (!selectedProjectId) return;
    refreshProjectData(selectedProjectId).catch((err: unknown) => setError(String(err)));
  }, [selectedProjectId]);

  async function handleCreateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const project = await createProject({
        name: `${form.target_company.name} 尽调`,
        company_config: form,
      });
      setSelectedProjectId(project.id);
      await refreshProjects();
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleAddResource() {
    if (!selectedProjectId || !resourceValue.trim()) return;
    setLoading(true);
    setError("");
    try {
      await createResource(selectedProjectId, { type: "trusted_source", value: resourceValue });
      await refreshProjectData(selectedProjectId);
      setResourceValue("");
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleStartRun() {
    if (!selectedProjectId) return;
    setLoading(true);
    setError("");
    try {
      const started = await startRun(selectedProjectId);
      const latest = await getRun(started.id);
      setRun(latest);
      await refreshProjectData(selectedProjectId);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">AgentScope Due Diligence Workspace</p>
          <h1>尽调平台</h1>
          <p>配置通用 agent 流程，并按目标公司注入资源后执行尽调。</p>
        </div>
        <button disabled={!selectedProjectId || loading} onClick={handleStartRun}>
          {loading ? "处理中..." : "启动尽调 Run"}
        </button>
      </header>

      {error ? <div className="error">{error}</div> : null}

      <div className="grid two">
        <SectionCard title="新建尽调项目" description="填写目标公司和本次尽调范围。">
          <form className="form" onSubmit={handleCreateProject}>
            <label>
              尽调流程模板
              <select
                value={form.scope.workflow_id}
                onChange={(event) => {
                  const workflow = workflowTemplates.find((item) => item.id === event.target.value);
                  if (!workflow) return;
                  setForm({
                    ...form,
                    scope: {
                      ...form.scope,
                      workflow_id: workflow.id,
                      workflow_template_id: workflow.id,
                      workflow_template_version: workflow.version,
                      scenario: workflow.scenario,
                      focus_areas: focusAreasForScenario(workflow.scenario),
                    },
                  });
                }}
              >
                {workflowTemplates.map((workflow) => (
                  <option key={workflow.id} value={workflow.id}>
                    {workflow.name} v{workflow.version}
                  </option>
                ))}
              </select>
            </label>
            <label>
              公司名称
              <input
                value={form.target_company.name}
                onChange={(event) =>
                  setForm({ ...form, target_company: { ...form.target_company, name: event.target.value } })
                }
              />
            </label>
            <label>
              官网
              <input
                value={form.target_company.website}
                onChange={(event) =>
                  setForm({ ...form, target_company: { ...form.target_company, website: event.target.value } })
                }
              />
            </label>
            <label>
              行业
              <input
                value={form.target_company.industry}
                onChange={(event) =>
                  setForm({ ...form, target_company: { ...form.target_company, industry: event.target.value } })
                }
              />
            </label>
            <label>
              关键词，逗号分隔
              <input
                value={form.target_company.keywords.join(", ")}
                onChange={(event) =>
                  setForm({ ...form, target_company: { ...form.target_company, keywords: splitList(event.target.value) } })
                }
              />
            </label>
            <label>
              关注范围，逗号分隔
              <input
                value={form.scope.focus_areas.join(", ")}
                onChange={(event) =>
                  setForm({ ...form, scope: { ...form.scope, focus_areas: splitList(event.target.value) } })
                }
              />
            </label>
            <button type="submit" disabled={loading}>
              创建项目
            </button>
          </form>
        </SectionCard>

        <SectionCard title="项目与资源" description="选择项目，并补充可信来源或材料引用。">
          <label>
            当前项目
            <select value={selectedProjectId} onChange={(event) => setSelectedProjectId(event.target.value)}>
              <option value="">请选择</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>
          {selectedProject ? (
            <div className="summary-box">
              <strong>{selectedProject.company_config.target_company.name}</strong>
              <span>
                {workflowName(
                  selectedProject.company_config.scope.workflow_template_id ?? selectedProject.company_config.scope.workflow_id,
                  workflowTemplates,
                )}
              </span>
            </div>
          ) : null}
          <div className="inline-form">
            <input value={resourceValue} onChange={(event) => setResourceValue(event.target.value)} />
            <button onClick={handleAddResource} disabled={!selectedProjectId || loading}>
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
      </div>

      <div className="grid three">
        <SectionCard title="Agent 执行状态">
          {run?.steps.length ? (
            <ol className="timeline">
              {run.steps.map((step) => (
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
          {evidence.length ? (
            <ul className="list evidence-list">
              {evidence.map((item) => (
                <li key={item.id}>
                  <span>{item.collected_by}</span>
                  <strong>{item.title}</strong>
                  <p>{item.excerpt}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">暂无证据。</p>
          )}
        </SectionCard>

        <SectionCard title="尽调报告">
          {reports[0] ? (
            <article className="report">
              <h3>{reports[0].title}</h3>
              <span className={`risk ${reports[0].overall_risk}`}>整体风险：{reports[0].overall_risk}</span>
              <p>{reports[0].executive_summary}</p>
              {reports[0].sections.map((section) => (
                <div key={section.title} className="report-section">
                  <strong>{section.title}</strong>
                  <p>{section.summary}</p>
                </div>
              ))}
            </article>
          ) : (
            <p className="muted">完成 run 后生成报告。</p>
          )}
        </SectionCard>
      </div>
    </main>
  );
}
