import type { CompanyConfig } from "../types/domain";

export function workflowTemplateIdFromConfig(config: CompanyConfig): string {
  return (config.workflow_template_id ?? "").trim();
}

export function normalizeCompanyConfig(raw: CompanyConfig): CompanyConfig {
  return {
    target_company: raw.target_company,
    workflow_template_id: workflowTemplateIdFromConfig(raw),
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
  };
}
