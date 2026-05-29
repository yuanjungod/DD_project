import { FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { createEngagement, getEngagement, listWorkflowTemplates, updateEngagement } from "../api/client";
import { EngagementAgentOverridesPanel } from "../components/EngagementAgentOverridesPanel";
import { EngagementResourceCatalogPanel } from "../components/EngagementResourceCatalogPanel";
import { SectionCard } from "../components/SectionCard";
import { engagementIdentityLabel } from "../domain/engagementIdentity";
import { ENGAGEMENT_LABELS } from "../domain/engagementLabels";
import { workflowTemplateIdFromInstance } from "../domain/instanceConfig";
import {
  instanceConfigToForm,
  taskNameFromConfig,
  toInstanceConfigPayload,
  type EngagementSetupForm,
} from "../domain/instanceConfig";
import type { Engagement, WorkflowTemplate } from "../types/domain";

function defaultConfig(workflowTemplateId: string): EngagementSetupForm {
  return {
    task_name: "",
    workflow_task: "",
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

const WIZARD_STEPS: Array<{ step: WizardStep; label: string; short: string; hint: string }> = [
  { step: "identity", label: "任务定义", short: "1", hint: "描述要完成的工作" },
  { step: "resources", label: "实例资源", short: "2", hint: "文件与来源" },
  { step: "agents", label: "Agent 配置", short: "3", hint: "步骤级覆盖" },
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
    <nav className="create-app-wizard-nav" aria-label="创建任务步骤">
      {WIZARD_STEPS.map((item, index) => {
        const locked = !engagementCreated && item.step !== "identity";
        const done = engagementCreated && index === 0;
        return (
          <button
            key={item.step}
            type="button"
            className={`create-app-wizard-nav__item ${currentStep === item.step ? "is-active" : ""} ${done && currentStep !== item.step ? "is-done" : ""}`}
            disabled={locked}
            aria-current={currentStep === item.step ? "step" : undefined}
            onClick={() => onStep(item.step)}
          >
            <span className="create-app-wizard-nav__short">{item.short}</span>
            <span className="create-app-wizard-nav__text">
              <span className="create-app-wizard-nav__label">{item.label}</span>
              <span className="create-app-wizard-nav__hint">{item.hint}</span>
            </span>
          </button>
        );
      })}
    </nav>
  );
}

export function NewEngagementPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialWorkflow = searchParams.get("workflow") ?? "";
  const resumeEngagementId = searchParams.get("engagement")?.trim() ?? "";

  const [form, setForm] = useState<EngagementSetupForm>(() => defaultConfig(initialWorkflow));
  const [workflowTemplates, setWorkflowTemplates] = useState<WorkflowTemplate[]>([]);
  const [createdEngagement, setCreatedEngagement] = useState<Engagement | null>(null);
  const [wizardStep, setWizardStep] = useState<WizardStep>(() => parseWizardStep(searchParams.get("step")) ?? "identity");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [booting, setBooting] = useState(Boolean(resumeEngagementId));

  const selectedWorkflow = useMemo(
    () => workflowTemplates.find((workflow) => workflow.id === workflowTemplateIdFromInstance(form)) ?? workflowTemplates[0],
    [form, workflowTemplates],
  );

  const workflowTemplateId = createdEngagement
    ? workflowTemplateIdFromInstance(createdEngagement.instance_config)
    : workflowTemplateIdFromInstance(form);

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
        setForm(instanceConfigToForm(engagement.instance_config));
        const step = parseWizardStep(searchParams.get("step")) ?? "identity";
        setWizardStep(step);
      })
      .catch((err: unknown) => setError(String(err)))
      .finally(() => setBooting(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- resume once on engagement id
  }, [resumeEngagementId]);

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
    setForm(instanceConfigToForm(engagement.instance_config));
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
    if (!workflowTemplateIdFromInstance(form)) {
      setError("请先选择已发布的 Workflow 模板。");
      setLoading(false);
      return;
    }
    if (!form.task_name.trim()) {
      setError("请填写任务名称。");
      setLoading(false);
      return;
    }
    if (!form.workflow_task.trim()) {
      setError("请填写需要完成的任务。");
      setLoading(false);
      return;
    }
    const taskName = form.task_name.trim();
    const displayName = `${taskName} · ${selectedWorkflow?.name ?? "应用"}`;
    const instance_config = toInstanceConfigPayload(form);
    try {
      if (createdEngagement) {
        const engagement = await updateEngagement(createdEngagement.id, {
          name: displayName,
          instance_config,
        });
        setCreatedEngagement(engagement);
        hydrateIdentityFromEngagement(engagement);
      } else {
        const engagement = await createEngagement({
          name: displayName,
          instance_config,
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
          <p className="eyebrow">{ENGAGEMENT_LABELS.createPageEyebrow}</p>
          <h1>{ENGAGEMENT_LABELS.loadingConfig}</h1>
        </header>
      </div>
    );
  }

  return (
    <div className="page-stack engagement-wizard-page">
      <header className={`page-hero ${createdEngagement ? "" : "page-hero--compact"}`}>
        <p className="eyebrow">{createdEngagement ? ENGAGEMENT_LABELS.editEyebrow : ENGAGEMENT_LABELS.newEyebrow}</p>
        <h1>{createdEngagement ? engagementIdentityLabel(createdEngagement) : "定义一次工作流运行"}</h1>
        <p className="page-hero__lede">
          {createdEngagement ? (
            <>
              任务「{taskNameFromConfig(createdEngagement.instance_config) || createdEngagement.name}」· 版本 v
              {createdEngagement.version}。可在下方步骤间切换并保存；启动运行请至「{ENGAGEMENT_LABELS.listNav}」。
            </>
          ) : (
            "填写任务名称与任务说明，选择模板后即可创建；应用标识由系统自动生成。"
          )}
        </p>
      </header>

      <CreateAppWizardNav currentStep={wizardStep} engagementCreated={Boolean(createdEngagement)} onStep={goToStep} />

      {error ? <div className="error engagement-wizard-error">{error}</div> : null}

      {wizardStep === "identity" ? (
        <section className="engagement-setup-card">
          <header className="engagement-setup-card__header">
            <div>
              <p className="engagement-setup-card__eyebrow">{stepMeta.short} · {stepMeta.label}</p>
              <h2>{createdEngagement ? "更新任务定义" : "描述任务并创建"}</h2>
              <p>
                已选模板 <strong>{selectedWorkflow?.name ?? "未选择"}</strong>
                {selectedWorkflow ? ` · v${selectedWorkflow.version}` : null}
              </p>
            </div>
            {selectedWorkflow?.description ? (
              <p className="engagement-setup-card__template-desc">{selectedWorkflow.description}</p>
            ) : null}
          </header>

          <form className="engagement-setup-form" onSubmit={(e) => void handleSaveIdentity(e)}>
            <div className="engagement-meta-grid">
              <label className="engagement-meta-field engagement-meta-field--span-2">
                <span className="engagement-field-label">
                  任务名称 <span className="required-dot">*</span>
                </span>
                <input
                  value={form.task_name}
                  onChange={(event) => setForm({ ...form, task_name: event.target.value })}
                  placeholder="例如：某某公司成长能力分析"
                  required
                  maxLength={120}
                />
                <span className="engagement-field-hint">在列表与页头展示；用于区分不同任务。</span>
              </label>

              <label className="engagement-meta-field">
                <span className="engagement-field-label">工作流模板</span>
                <select
                  value={workflowTemplateIdFromInstance(form)}
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
                      {workflow.name} · v{workflow.version}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="engagement-task-panel">
              <div className="engagement-task-panel__head">
                <label htmlFor="engagement-workflow-task" className="engagement-field-label">
                  需要完成的任务 <span className="required-dot">*</span>
                </label>
                <span className="engagement-task-panel__badge">注入全部 Agent</span>
              </div>
              <textarea
                id="engagement-workflow-task"
                className="engagement-task-panel__input"
                value={form.workflow_task}
                onChange={(event) => setForm({ ...form, workflow_task: event.target.value })}
                placeholder={"用自然语言描述本次工作流要完成的具体任务。\n\n例如：对某某公司完成成长能力分析，梳理近三年营收结构、核心竞争壁垒与主要风险，并输出可交付的分析报告。"}
                rows={6}
                required
              />
              <p className="engagement-field-hint">
                这段描述会作为<strong>最终目标</strong>写入每个 Agent 的任务上下文，请尽量具体、可执行。
              </p>
            </div>

            <div className="engagement-form-actions">
              <p className="engagement-form-actions__note">
                {createdEngagement
                  ? "保存后不影响已登记的资源与 Agent 覆盖。"
                  : "创建后可继续配置资源与 Agent，无需按顺序完成。"}
              </p>
              <button type="submit" className="engagement-form-actions__submit" disabled={loading}>
                {loading ? "保存中…" : createdEngagement ? "保存更改" : "创建任务"}
              </button>
            </div>
          </form>
        </section>
      ) : null}

      {wizardStep === "resources" && createdEngagement ? (
        <EngagementResourceCatalogPanel engagementId={createdEngagement.id} />
      ) : null}

      {wizardStep === "agents" && createdEngagement ? (
        <EngagementAgentOverridesPanel engagementId={createdEngagement.id} workflowTemplateId={workflowTemplateId} />
      ) : null}

      {wizardStep !== "identity" && !createdEngagement ? (
        <SectionCard title="请先创建任务">
          <p className="muted">请通过上方 Step 1 填写并创建任务后，再配置实例资源与 Agent。</p>
        </SectionCard>
      ) : null}
    </div>
  );
}
