import type { CompanyConfig } from "../types/domain";

/** Legacy nested scope on projects created before scope removal. */
type LegacyCompanyConfig = CompanyConfig & {
  scope?: {
    workflow_id?: string;
    workflow_template_id?: string | null;
    workflow_template_version?: number | null;
  };
};

export function workflowTemplateIdFromConfig(config: LegacyCompanyConfig): string {
  return (
    config.workflow_template_id ??
    config.workflow_id ??
    config.scope?.workflow_template_id ??
    config.scope?.workflow_id ??
    "standard_due_diligence"
  );
}

export function normalizeCompanyConfig(raw: LegacyCompanyConfig): CompanyConfig {
  const workflow_template_id = workflowTemplateIdFromConfig(raw);
  return {
    target_company: raw.target_company,
    workflow_id: raw.workflow_id ?? raw.scope?.workflow_id ?? workflow_template_id,
    workflow_template_id,
    workflow_template_version: raw.workflow_template_version ?? raw.scope?.workflow_template_version ?? null,
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
