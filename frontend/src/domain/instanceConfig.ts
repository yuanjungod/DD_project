import type { CompanyConfig, InstanceConfig } from "../types/domain";

export function isDueDiligenceTemplate(templateId: string): boolean {
  return templateId.includes("due_diligence");
}

export function workflowTemplateIdFromInstance(config: Pick<InstanceConfig, "workflow_template_id">): string {
  return (config.workflow_template_id ?? "").trim();
}

export function subjectNameFromConfig(config: CompanyConfig | InstanceConfig): string {
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
export function toInstanceConfigPayload(form: CompanyConfig): InstanceConfig {
  const templateId = form.workflow_template_id.trim();
  const base = {
    workflow_template_id: templateId,
    workflow_template_version: form.workflow_template_version ?? null,
    resources: form.resources,
  };
  if (isDueDiligenceTemplate(templateId)) {
    return {
      ...base,
      target_company: form.target_company,
      extensions: {
        due_diligence: { target_company: form.target_company },
      },
    };
  }
  return {
    ...base,
    extensions: {
      subject: {
        name: form.target_company.name,
        aliases: form.target_company.aliases,
        kind: "generic",
      },
    },
  };
}

export function instanceConfigToForm(config: InstanceConfig): CompanyConfig {
  const name = subjectNameFromConfig(config);
  const aliases =
    config.target_company?.aliases ??
    config.extensions?.subject?.aliases ??
    config.extensions?.due_diligence?.target_company?.aliases ??
    [];
  return {
    target_company: { name: name || "Untitled", aliases: [...aliases] },
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
