import type { Project } from "../types/domain";

export function projectIdentityLabel(project: Pick<Project, "company_config" | "application_id" | "version">): string {
  const company = project.company_config?.target_company?.name?.trim() || "尽调应用";
  return `${company} · ${project.application_id} · v${project.version}`;
}

export function projectTechnicalId(project: Pick<Project, "id">): string {
  return project.id;
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
