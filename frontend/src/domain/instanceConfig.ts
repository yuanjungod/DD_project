import type { CompanyConfig, InstanceConfig } from "../types/domain";

export type EngagementSetupForm = CompanyConfig & {
  workflow_task: string;
};

export function isDueDiligenceTemplate(templateId: string): boolean {
  return templateId.includes("due_diligence");
}

export function workflowTemplateIdFromInstance(config: Pick<InstanceConfig, "workflow_template_id">): string {
  return (config.workflow_template_id ?? "").trim();
}

export function workflowTaskFromConfig(config: CompanyConfig | InstanceConfig): string {
  const instance = config as InstanceConfig;
  const taskBlock = instance.extensions?.workflow_task;
  if (taskBlock && typeof taskBlock === "object") {
    for (const key of ["description", "task", "goal"] as const) {
      const text = taskBlock[key];
      if (typeof text === "string" && text.trim()) {
        return text.trim();
      }
    }
  }
  if ("workflow_task" in config && typeof (config as { workflow_task?: string }).workflow_task === "string") {
    const direct = (config as { workflow_task: string }).workflow_task.trim();
    if (direct) return direct;
  }
  if ("target_company" in config && config.target_company?.name) {
    return config.target_company.name.trim();
  }
  const subject = instance.extensions?.subject;
  if (subject && typeof subject.name === "string" && subject.name.trim()) {
    return subject.name.trim();
  }
  const dd = instance.extensions?.due_diligence?.target_company;
  if (dd && typeof dd.name === "string" && dd.name.trim()) {
    return dd.name.trim();
  }
  return "";
}

export function subjectNameFromConfig(config: CompanyConfig | InstanceConfig): string {
  const task = workflowTaskFromConfig(config);
  if (task) {
    const firstLine = task.split(/\r?\n/)[0]?.trim() ?? "";
    return (firstLine || task).slice(0, 120);
  }
  if ("target_company" in config && config.target_company?.name) {
    return config.target_company.name.trim();
  }
  const instance = config as InstanceConfig;
  const subject = instance.extensions?.subject;
  if (subject && typeof subject.name === "string") {
    return subject.name.trim();
  }
  const dd = instance.extensions?.due_diligence?.target_company;
  if (dd && typeof dd.name === "string") {
    return dd.name.trim();
  }
  return "";
}

export function normalizeInstanceConfig(raw: InstanceConfig): InstanceConfig {
  return {
    workflow_template_id: workflowTemplateIdFromInstance(raw),
    workflow_template_version: raw.workflow_template_version ?? null,
    resources: {
      uploaded_files: raw.resources?.uploaded_files ?? [],
      trusted_sources: raw.resources?.trusted_sources ?? [],
      blocked_sources: raw.resources?.blocked_sources ?? [],
      competitors: raw.resources?.competitors ?? [],
      metrics: raw.resources?.metrics ?? [],
      external_clues: raw.resources?.external_clues ?? [],
      agent_resource_scopes: raw.resources?.agent_resource_scopes ?? [],
    },
    extensions: raw.extensions ?? {},
    ...(raw.target_company ? { target_company: raw.target_company } : {}),
  };
}

/** Map wizard form state to API instance_config payload. */
export function toInstanceConfigPayload(form: EngagementSetupForm): InstanceConfig {
  const templateId = form.workflow_template_id.trim();
  const task = form.workflow_task.trim();
  const label = (task.split(/\r?\n/)[0]?.trim() || task || "Untitled").slice(0, 120);
  const targetCompany = { name: label, aliases: form.target_company.aliases };
  const base = {
    workflow_template_id: templateId,
    workflow_template_version: form.workflow_template_version ?? null,
    resources: form.resources,
    extensions: {
      workflow_task: { description: task },
    },
  };
  if (isDueDiligenceTemplate(templateId)) {
    return {
      ...base,
      target_company: targetCompany,
      extensions: {
        ...base.extensions,
        due_diligence: { target_company: targetCompany },
      },
    };
  }
  return base;
}

export function instanceConfigToForm(config: InstanceConfig): EngagementSetupForm {
  const task = workflowTaskFromConfig(config);
  const aliases =
    config.target_company?.aliases ??
    config.extensions?.subject?.aliases ??
    config.extensions?.due_diligence?.target_company?.aliases ??
    [];
  return {
    workflow_task: task,
    target_company: { name: subjectNameFromConfig(config) || "Untitled", aliases: [...aliases] },
    workflow_template_id: workflowTemplateIdFromInstance(config),
    workflow_template_version: config.workflow_template_version ?? null,
    resources: {
      uploaded_files: config.resources?.uploaded_files ?? [],
      trusted_sources: config.resources?.trusted_sources ?? [],
      blocked_sources: config.resources?.blocked_sources ?? [],
      competitors: config.resources?.competitors ?? [],
      metrics: config.resources?.metrics ?? [],
      external_clues: config.resources?.external_clues ?? [],
      agent_resource_scopes: config.resources?.agent_resource_scopes ?? [],
    },
  };
}
