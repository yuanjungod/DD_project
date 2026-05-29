import type { InstanceConfig } from "../types/domain";
import type { CompanyConfig } from "../types/domain";

export type EngagementSetupForm = {
  workflow_task: string;
  workflow_template_id: string;
  workflow_template_version?: number | null;
  resources: CompanyConfig["resources"];
};

export function workflowTemplateIdFromInstance(config: Pick<InstanceConfig, "workflow_template_id">): string {
  return (config.workflow_template_id ?? "").trim();
}

export function workflowTaskFromConfig(config: InstanceConfig): string {
  const taskBlock = config.extensions?.workflow_task;
  if (taskBlock && typeof taskBlock === "object") {
    for (const key of ["description", "task", "goal"] as const) {
      const text = taskBlock[key];
      if (typeof text === "string" && text.trim()) {
        return text.trim();
      }
    }
  }
  if (config.target_company?.name) {
    return config.target_company.name.trim();
  }
  const subject = config.extensions?.subject;
  if (subject && typeof subject.name === "string" && subject.name.trim()) {
    return subject.name.trim();
  }
  const dd = config.extensions?.due_diligence?.target_company;
  if (dd && typeof dd.name === "string" && dd.name.trim()) {
    return dd.name.trim();
  }
  return "";
}

export function subjectNameFromConfig(config: InstanceConfig | EngagementSetupForm): string {
  if ("workflow_task" in config && typeof config.workflow_task === "string") {
    const direct = config.workflow_task.trim();
    if (direct) {
      const firstLine = direct.split(/\r?\n/)[0]?.trim() ?? "";
      return (firstLine || direct).slice(0, 120);
    }
  }
  const task = workflowTaskFromConfig(config as InstanceConfig);
  if (task) {
    const firstLine = task.split(/\r?\n/)[0]?.trim() ?? "";
    return (firstLine || task).slice(0, 120);
  }
  return "";
}

/** Map wizard form state to API instance_config payload (normalization on backend). */
export function toInstanceConfigPayload(form: EngagementSetupForm): InstanceConfig {
  const task = form.workflow_task.trim();
  return {
    workflow_template_id: form.workflow_template_id.trim(),
    workflow_template_version: form.workflow_template_version ?? null,
    resources: form.resources,
    extensions: {
      workflow_task: { description: task },
    },
  };
}

export function instanceConfigToForm(config: InstanceConfig): EngagementSetupForm {
  return {
    workflow_task: workflowTaskFromConfig(config),
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
