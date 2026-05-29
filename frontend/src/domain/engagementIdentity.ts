import type { Engagement } from "../types/domain";
import { subjectNameFromConfig } from "./instanceConfig";

export function engagementConfig(engagement: Pick<Engagement, "instance_config" | "company_config">) {
  return engagement.instance_config ?? engagement.company_config;
}

export function engagementIdentityLabel(
  engagement: Pick<Engagement, "instance_config" | "company_config" | "application_id" | "version">,
): string {
  const company = subjectNameFromConfig(engagementConfig(engagement)) || "Engagement";
  return `${company} · ${engagement.application_id} · v${engagement.version}`;
}

export function engagementTechnicalId(engagement: Pick<Engagement, "id">): string {
  return engagement.id;
}

export function defaultApplicationId(companyName: string): string {
  const slug = companyName
    .trim()
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fff-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  if (/^[a-z]/.test(slug)) return slug.slice(0, 48);
  return `app-${Date.now().toString(36).slice(-6)}`;
}
