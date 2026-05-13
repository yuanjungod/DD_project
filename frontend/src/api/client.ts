import type { AgentRun, Evidence, Project, Report, Resource, CompanyConfig } from "../types/domain";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function listProjects(): Promise<Project[]> {
  return request<Project[]>("/projects");
}

export function createProject(payload: { name: string; company_config: CompanyConfig }): Promise<Project> {
  return request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listResources(projectId: string): Promise<Resource[]> {
  return request<Resource[]>(`/projects/${projectId}/resources`);
}

export function createResource(projectId: string, payload: { type: string; value: string }): Promise<Resource> {
  return request<Resource>(`/projects/${projectId}/resources`, {
    method: "POST",
    body: JSON.stringify({ ...payload, metadata_json: {} }),
  });
}

export function startRun(projectId: string): Promise<AgentRun> {
  return request<AgentRun>(`/projects/${projectId}/runs`, { method: "POST" });
}

export function getRun(runId: string): Promise<AgentRun> {
  return request<AgentRun>(`/runs/${runId}`);
}

export function listEvidence(projectId: string): Promise<Evidence[]> {
  return request<Evidence[]>(`/projects/${projectId}/evidence`);
}

export function listReports(projectId: string): Promise<Report[]> {
  return request<Report[]>(`/projects/${projectId}/reports`);
}
