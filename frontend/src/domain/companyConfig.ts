import type { CompanyConfig, InstanceConfig } from "../types/domain";

export function workflowTemplateIdFromConfig(config: CompanyConfig | InstanceConfig): string {
  return (config.workflow_template_id ?? "").trim();
}
