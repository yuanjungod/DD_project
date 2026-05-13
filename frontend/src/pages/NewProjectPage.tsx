import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { createProject, listWorkflowTemplates } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import { workflowOptions } from "../data/workflows";
import type { CompanyConfig, WorkflowTemplate } from "../types/domain";

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function defaultConfig(workflowId: string): CompanyConfig {
  const workflow = workflowOptions.find((item) => item.id === workflowId) ?? workflowOptions[0];
  return {
    target_company: {
      name: "Example Robotics",
      aliases: ["ExampleBot"],
      website: "https://example.com",
      jurisdiction: "中国大陆",
      industry: "智能制造",
      keywords: ["仓储自动化", "机器人"],
    },
    scope: {
      workflow_id: workflow.id,
      workflow_template_id: workflow.id,
      workflow_template_version: 1,
      scenario: workflow.scenario,
      time_range: "近5年",
      focus_areas: workflow.focusAreas,
      report_language: "zh-CN",
    },
    resources: {
      uploaded_files: [],
      trusted_sources: ["公司官网", "交易所公告", "工商登记信息"],
      blocked_sources: [],
      competitors: ["Peer Robotics", "Warehouse AI"],
    },
  };
}

export function NewProjectPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialWorkflow = searchParams.get("workflow") ?? "standard_due_diligence";
  const [form, setForm] = useState<CompanyConfig>(() => defaultConfig(initialWorkflow));
  const [workflowTemplates, setWorkflowTemplates] = useState<WorkflowTemplate[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const selectedWorkflow = useMemo(
    () => workflowTemplates.find((workflow) => workflow.id === form.scope.workflow_template_id) ?? workflowTemplates[0],
    [form.scope.workflow_template_id, workflowTemplates],
  );

  useEffect(() => {
    listWorkflowTemplates()
      .then((items) => {
        const published = items.filter((item) => item.status === "published");
        setWorkflowTemplates(published);
        const selected = published.find((item) => item.id === initialWorkflow) ?? published[0];
        if (selected) {
          setForm((current) => ({
            ...current,
            scope: {
              ...current.scope,
              workflow_id: selected.id,
              workflow_template_id: selected.id,
              workflow_template_version: selected.version,
              scenario: selected.scenario,
              focus_areas: focusAreasForScenario(selected.scenario),
            },
          }));
        }
      })
      .catch((err: unknown) => setError(String(err)));
  }, [initialWorkflow]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const project = await createProject({
        name: `${form.target_company.name} - ${selectedWorkflow?.name ?? "尽调应用"}`,
        company_config: form,
      });
      navigate(`/projects/${project.id}`);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Step 2</p>
        <h1>场景的具体应用</h1>
        <p>选择一个可复用尽调场景，再填入具体公司、资源和关注范围。</p>
      </header>
      {error ? <div className="error">{error}</div> : null}
      <SectionCard title="创建公司尽调应用" description={`当前流程：${selectedWorkflow?.name ?? "未选择"}`}>
        <form className="form split-form" onSubmit={handleCreate}>
          <label>
            尽调场景
            <select
              value={form.scope.workflow_template_id ?? form.scope.workflow_id}
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
              onChange={(event) => setForm({ ...form, target_company: { ...form.target_company, name: event.target.value } })}
            />
          </label>
          <label>
            官网
            <input
              value={form.target_company.website}
              onChange={(event) => setForm({ ...form, target_company: { ...form.target_company, website: event.target.value } })}
            />
          </label>
          <label>
            行业
            <input
              value={form.target_company.industry}
              onChange={(event) => setForm({ ...form, target_company: { ...form.target_company, industry: event.target.value } })}
            />
          </label>
          <label>
            关键词
            <input
              value={form.target_company.keywords.join(", ")}
              onChange={(event) =>
                setForm({ ...form, target_company: { ...form.target_company, keywords: splitList(event.target.value) } })
              }
            />
          </label>
          <label>
            关注范围
            <input
              value={form.scope.focus_areas.join(", ")}
              onChange={(event) => setForm({ ...form, scope: { ...form.scope, focus_areas: splitList(event.target.value) } })}
            />
          </label>
          <button disabled={loading}>{loading ? "创建中..." : "创建应用"}</button>
        </form>
      </SectionCard>
    </div>
  );
}

function focusAreasForScenario(scenario: string): string[] {
  return workflowOptions.find((workflow) => workflow.scenario === scenario)?.focusAreas ?? ["业务", "财务", "法律", "合规"];
}
