import { FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { createEngagement, getEngagement, listWorkflowTemplates, updateEngagement } from "../api/client";
import { EngagementAgentOverridesPanel } from "../components/EngagementAgentOverridesPanel";
import { EngagementResourceCatalogPanel } from "../components/EngagementResourceCatalogPanel";
import { SectionCard } from "../components/SectionCard";
import { defaultApplicationId, engagementIdentityLabel } from "../domain/engagementIdentity";
import { normalizeCompanyConfig, workflowTemplateIdFromConfig } from "../domain/companyConfig";
import type { CompanyConfig, Engagement, WorkflowTemplate } from "../types/domain";

function defaultConfig(workflowTemplateId: string): CompanyConfig {
  return {
    target_company: {
      name: "Example Robotics",
      aliases: ["ExampleBot"],
    },
    workflow_template_id: workflowTemplateId,
    workflow_template_version: 1,
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
  engagementCreated,
  onStep,
}: {
  currentStep: WizardStep;
  engagementCreated: boolean;
  onStep: (step: WizardStep) => void;
}) {
  return (
    <nav className="create-app-wizard-nav" aria-label="创建 Engagement 步骤">
      {WIZARD_STEPS.map((item) => {
        const locked = !engagementCreated && item.step !== "identity";
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

export function NewEngagementPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialWorkflow = searchParams.get("workflow") ?? "standard_due_diligence";
  const resumeEngagementId = searchParams.get("engagement")?.trim() ?? "";

  const [form, setForm] = useState<CompanyConfig>(() => defaultConfig(initialWorkflow));
  const [applicationId, setApplicationId] = useState("");
  const [workflowTemplates, setWorkflowTemplates] = useState<WorkflowTemplate[]>([]);
  const [createdEngagement, setCreatedEngagement] = useState<Engagement | null>(null);
  const [wizardStep, setWizardStep] = useState<WizardStep>(() => parseWizardStep(searchParams.get("step")) ?? "identity");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [booting, setBooting] = useState(Boolean(resumeEngagementId));

  const selectedWorkflow = useMemo(
    () => workflowTemplates.find((workflow) => workflow.id === workflowTemplateIdFromConfig(form)) ?? workflowTemplates[0],
    [form, workflowTemplates],
  );

  const workflowTemplateId = createdEngagement
    ? workflowTemplateIdFromConfig(createdEngagement.company_config)
    : workflowTemplateIdFromConfig(form);

  useEffect(() => {
    listWorkflowTemplates()
      .then((items) => {
        const published = items.filter((item) => item.status === "published");
        setWorkflowTemplates(published);
        if (createdEngagement || resumeEngagementId) return;
        const selected = published.find((item) => item.id === initialWorkflow) ?? published[0];
        if (selected) {
          setForm((current) => ({
            ...current,
            workflow_template_id: selected.id,
            workflow_template_version: selected.version,
          }));
        }
      })
      .catch((err: unknown) => setError(String(err)));
  }, [initialWorkflow, createdEngagement, resumeEngagementId]);

  useEffect(() => {
    if (!resumeEngagementId) {
      setBooting(false);
      return;
    }
    setBooting(true);
    setError("");
    getEngagement(resumeEngagementId)
      .then((engagement) => {
        setCreatedEngagement(engagement);
        setForm(normalizeCompanyConfig(engagement.company_config));
        setApplicationId(engagement.application_id);
        const step = parseWizardStep(searchParams.get("step")) ?? "identity";
        setWizardStep(step);
      })
      .catch((err: unknown) => setError(String(err)))
      .finally(() => setBooting(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- resume once on engagement id
  }, [resumeEngagementId]);

  useEffect(() => {
    if (!applicationId && form.target_company.name.trim() && !createdEngagement) {
      setApplicationId(defaultApplicationId(form.target_company.name));
    }
  }, [form.target_company.name, applicationId, createdEngagement]);

  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    if (createdEngagement) {
      next.set("engagement", createdEngagement.id);
      next.set("step", wizardStep);
    } else {
      next.delete("engagement");
      if (wizardStep === "identity") next.delete("step");
      else next.set("step", wizardStep);
    }
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sync URL with wizard state
  }, [createdEngagement?.id, wizardStep]);

  function hydrateIdentityFromEngagement(engagement: Engagement) {
    setForm(normalizeCompanyConfig(engagement.company_config));
    setApplicationId(engagement.application_id);
  }

  function goToStep(step: WizardStep) {
    if (!createdEngagement && step !== "identity") return;
    if (step === "identity" && createdEngagement) {
      hydrateIdentityFromEngagement(createdEngagement);
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
      if (createdEngagement) {
        const engagement = await updateEngagement(createdEngagement.id, {
          name: displayName,
          company_config: form,
          application_id: applicationId.trim(),
        });
        setCreatedEngagement(engagement);
        hydrateIdentityFromEngagement(engagement);
      } else {
        const engagement = await createEngagement({
          name: displayName,
          company_config: form,
          application_id: applicationId.trim(),
        });
        setCreatedEngagement(engagement);
        hydrateIdentityFromEngagement(engagement);
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
          <p className="eyebrow">创建 Engagement</p>
          <h1>加载 Engagement 配置…</h1>
        </header>
      </div>
    );
  }

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">{createdEngagement ? "创建 Engagement · 可随时修改" : "创建 Engagement"}</p>
        <h1>{createdEngagement ? engagementIdentityLabel(createdEngagement) : "工作流模板的具体 Engagement"}</h1>
        <p>
          {createdEngagement ? (
            <>
              应用标识符 <code>{createdEngagement.application_id}</code> · 技术 ID <code>{createdEngagement.id}</code>
              。通过上方步骤栏切换各配置页，修改后保存即可；Run 请至「Engagements」启动。
            </>
          ) : (
            "填写公司与应用标识并创建后，可在公司资源与 Agent 配置之间来回调整，无需按固定顺序完成。"
          )}
        </p>
      </header>

      <CreateAppWizardNav currentStep={wizardStep} engagementCreated={Boolean(createdEngagement)} onStep={goToStep} />

      {error ? <div className="error">{error}</div> : null}

      {wizardStep === "identity" ? (
        <SectionCard
          title={`${stepMeta.short} · ${stepMeta.label}`}
          description={
            createdEngagement
              ? `更新工作流模板与应用标识（${selectedWorkflow?.name ?? "未选择"}）；保存后不影响已登记的资源与 Agent 配置。`
              : `选择工作流模板并填写应用标识（${selectedWorkflow?.name ?? "未选择"}）。`
          }
        >
          <form className="form split-form" onSubmit={(e) => void handleSaveIdentity(e)}>
            <div className="form-section">
              <h3 className="form-section__title">基础配置</h3>
              <label>
                工作流模板
                <select
                  value={workflowTemplateIdFromConfig(form)}
                  onChange={(event) => {
                    const workflow = workflowTemplates.find((item) => item.id === event.target.value);
                    if (!workflow) return;
                    setForm({
                      ...form,
                      workflow_template_id: workflow.id,
                      workflow_template_version: workflow.version,
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
            </div>

            <div className="inline-form" style={{ flexWrap: "wrap" }}>
              <button type="submit" disabled={loading}>
                {loading ? "保存中…" : createdEngagement ? "保存 Engagement" : "创建 Engagement"}
              </button>
            </div>
          </form>
        </SectionCard>
      ) : null}

      {wizardStep === "resources" && createdEngagement ? (
        <EngagementResourceCatalogPanel engagementId={createdEngagement.id} />
      ) : null}

      {wizardStep === "agents" && createdEngagement ? (
        <EngagementAgentOverridesPanel engagementId={createdEngagement.id} workflowTemplateId={workflowTemplateId} />
      ) : null}

      {wizardStep !== "identity" && !createdEngagement ? (
        <SectionCard title="请先创建 Engagement">
          <p className="muted">请通过上方 Step 1 填写并创建 Engagement 后，再配置公司资源与 Agent。</p>
        </SectionCard>
      ) : null}
    </div>
  );
}
