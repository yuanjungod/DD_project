import { FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { createProject, getProject, listWorkflowTemplates, updateProject } from "../api/client";
import { ProjectAgentOverridesPanel } from "../components/ProjectAgentOverridesPanel";
import { ProjectResourceCatalogPanel } from "../components/ProjectResourceCatalogPanel";
import { SectionCard } from "../components/SectionCard";
import { defaultApplicationId, projectIdentityLabel } from "../domain/projectIdentity";
import { focusAreasForScenario } from "../data/workflows";
import type { CompanyConfig, Project, WorkflowTemplate } from "../types/domain";

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function defaultConfig(workflowId: string): CompanyConfig {
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
      workflow_id: workflowId,
      workflow_template_id: workflowId,
      workflow_template_version: 1,
      scenario: "standard",
      time_range: "近5年",
      focus_areas: focusAreasForScenario("standard"),
      report_language: "zh-CN",
    },
    resources: {
      uploaded_files: [],
      trusted_sources: [],
      blocked_sources: [],
      competitors: [],
      metrics: [],
      external_clues: [],
    },
  };
}

type WizardStep = "identity" | "resources" | "agents";

const WIZARD_STEPS: Array<{ step: WizardStep; label: string; short: string }> = [
  { step: "identity", label: "公司与应用", short: "Step 1" },
  { step: "resources", label: "公司资源", short: "Step 2" },
  { step: "agents", label: "Agent 配置", short: "Step 3" },
];

function parseWizardStep(value: string | null): WizardStep | null {
  if (value === "identity" || value === "resources" || value === "agents") return value;
  return null;
}

function CreateAppWizardNav({
  currentStep,
  projectCreated,
  onStep,
}: {
  currentStep: WizardStep;
  projectCreated: boolean;
  onStep: (step: WizardStep) => void;
}) {
  return (
    <nav className="create-app-wizard-nav" aria-label="创建应用步骤">
      {WIZARD_STEPS.map((item) => {
        const locked = !projectCreated && item.step !== "identity";
        return (
          <button
            key={item.step}
            type="button"
            className={`create-app-wizard-nav__item ${currentStep === item.step ? "is-active" : ""}`}
            disabled={locked}
            aria-current={currentStep === item.step ? "step" : undefined}
            onClick={() => onStep(item.step)}
          >
            <span className="create-app-wizard-nav__short">{item.short}</span>
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

export function NewProjectPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialWorkflow = searchParams.get("workflow") ?? "standard_due_diligence";
  const resumeProjectId = searchParams.get("project")?.trim() ?? "";

  const [form, setForm] = useState<CompanyConfig>(() => defaultConfig(initialWorkflow));
  const [applicationId, setApplicationId] = useState("");
  const [workflowTemplates, setWorkflowTemplates] = useState<WorkflowTemplate[]>([]);
  const [createdProject, setCreatedProject] = useState<Project | null>(null);
  const [wizardStep, setWizardStep] = useState<WizardStep>(() => parseWizardStep(searchParams.get("step")) ?? "identity");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [booting, setBooting] = useState(Boolean(resumeProjectId));

  const selectedWorkflow = useMemo(
    () => workflowTemplates.find((workflow) => workflow.id === form.scope.workflow_template_id) ?? workflowTemplates[0],
    [form.scope.workflow_template_id, workflowTemplates],
  );

  const workflowTemplateId =
    createdProject?.company_config.scope.workflow_template_id ?? createdProject?.company_config.scope.workflow_id;

  useEffect(() => {
    listWorkflowTemplates()
      .then((items) => {
        const published = items.filter((item) => item.status === "published");
        setWorkflowTemplates(published);
        if (createdProject || resumeProjectId) return;
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
  }, [initialWorkflow, createdProject, resumeProjectId]);

  useEffect(() => {
    if (!resumeProjectId) {
      setBooting(false);
      return;
    }
    setBooting(true);
    setError("");
    getProject(resumeProjectId)
      .then((project) => {
        setCreatedProject(project);
        setForm(project.company_config);
        setApplicationId(project.application_id);
        const step = parseWizardStep(searchParams.get("step")) ?? "identity";
        setWizardStep(step);
      })
      .catch((err: unknown) => setError(String(err)))
      .finally(() => setBooting(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- resume once on project id
  }, [resumeProjectId]);

  useEffect(() => {
    if (!applicationId && form.target_company.name.trim() && !createdProject) {
      setApplicationId(defaultApplicationId(form.target_company.name));
    }
  }, [form.target_company.name, applicationId, createdProject]);

  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    if (createdProject) {
      next.set("project", createdProject.id);
      next.set("step", wizardStep);
    } else {
      next.delete("project");
      if (wizardStep === "identity") next.delete("step");
      else next.set("step", wizardStep);
    }
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sync URL with wizard state
  }, [createdProject?.id, wizardStep]);

  function hydrateIdentityFromProject(project: Project) {
    setForm(project.company_config);
    setApplicationId(project.application_id);
  }

  function goToStep(step: WizardStep) {
    if (!createdProject && step !== "identity") return;
    if (step === "identity" && createdProject) {
      hydrateIdentityFromProject(createdProject);
    }
    setWizardStep(step);
    setError("");
  }

  async function handleSaveIdentity(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    const displayName = `${form.target_company.name} - ${selectedWorkflow?.name ?? "尽调应用"}`;
    try {
      if (createdProject) {
        const project = await updateProject(createdProject.id, {
          name: displayName,
          company_config: form,
          application_id: applicationId.trim(),
        });
        setCreatedProject(project);
        hydrateIdentityFromProject(project);
      } else {
        const project = await createProject({
          name: displayName,
          company_config: form,
          application_id: applicationId.trim(),
        });
        setCreatedProject(project);
        hydrateIdentityFromProject(project);
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  const stepMeta = WIZARD_STEPS.find((item) => item.step === wizardStep)!;

  if (booting) {
    return (
      <div className="page-stack">
        <header className="page-hero">
          <p className="eyebrow">创建应用</p>
          <h1>加载应用配置…</h1>
        </header>
      </div>
    );
  }

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">{createdProject ? "创建应用 · 可随时修改" : "创建应用"}</p>
        <h1>{createdProject ? projectIdentityLabel(createdProject) : "场景的具体应用"}</h1>
        <p>
          {createdProject ? (
            <>
              应用标识符 <code>{createdProject.application_id}</code> · 技术 ID <code>{createdProject.id}</code>
              。通过上方步骤栏切换各配置页，修改后保存即可；Run 请至「场景应用」启动。
            </>
          ) : (
            "填写公司与应用标识并创建后，可在公司资源与 Agent 配置之间来回调整，无需按固定顺序完成。"
          )}
        </p>
      </header>

      <CreateAppWizardNav currentStep={wizardStep} projectCreated={Boolean(createdProject)} onStep={goToStep} />

      {error ? <div className="error">{error}</div> : null}

      {wizardStep === "identity" ? (
        <SectionCard
          title={`${stepMeta.short} · ${stepMeta.label}`}
          description={
            createdProject
              ? `更新公司与场景信息（${selectedWorkflow?.name ?? "未选择"}）；保存后不影响已登记的资源与 Agent 配置。`
              : `选择尽调场景并填写公司与应用标识（${selectedWorkflow?.name ?? "未选择"}）。`
          }
        >
          <form className="form split-form" onSubmit={(e) => void handleSaveIdentity(e)}>
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
                required
              />
            </label>
            <label>
              应用 ID（唯一标识符，小写英文/数字/连字符）
              <input
                value={applicationId}
                onChange={(event) => setApplicationId(event.target.value)}
                placeholder="mashang-standard-dd"
                required
                pattern="[a-z][a-z0-9_-]{0,62}"
                title="以小写字母开头，仅含小写字母、数字、下划线或连字符"
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
            <div className="inline-form" style={{ flexWrap: "wrap" }}>
              <button type="submit" disabled={loading}>
                {loading ? "保存中…" : createdProject ? "保存公司与应用" : "创建应用"}
              </button>
            </div>
          </form>
        </SectionCard>
      ) : null}

      {wizardStep === "resources" && createdProject ? (
        <ProjectResourceCatalogPanel projectId={createdProject.id} />
      ) : null}

      {wizardStep === "agents" && createdProject ? (
        <ProjectAgentOverridesPanel projectId={createdProject.id} workflowTemplateId={workflowTemplateId} />
      ) : null}

      {wizardStep !== "identity" && !createdProject ? (
        <SectionCard title="请先创建应用">
          <p className="muted">请通过上方 Step 1 填写并创建应用后，再配置公司资源与 Agent。</p>
        </SectionCard>
      ) : null}
    </div>
  );
}
