import type {
  AgentRun,
  AgentTemplate,
  AuthSession,
  CompanyConfig,
  Evidence,
  Project,
  Report,
  Resource,
  ResourceConfig,
  Scenario,
  SkillDebugResult,
  SkillPackage,
  ToolConfig,
  User,
  WorkflowTemplate,
} from "../types/domain";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem("dd_access_token");
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
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

export function login(payload: { email: string; password: string }): Promise<AuthSession> {
  return request<AuthSession>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getMe(): Promise<User> {
  return request<User>("/auth/me");
}

export function listScenarios(): Promise<Scenario[]> {
  return request<Scenario[]>("/scenarios");
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

export function listRuns(): Promise<AgentRun[]> {
  return request<AgentRun[]>("/runs");
}

export function listProjectRuns(projectId: string): Promise<AgentRun[]> {
  return request<AgentRun[]>(`/projects/${projectId}/runs`);
}

export function listSkills(): Promise<SkillPackage[]> {
  return request<SkillPackage[]>("/skills");
}

export function getSkill(skillId: string): Promise<SkillPackage> {
  return request<SkillPackage>(`/skills/${skillId}`);
}

export function createSkill(payload: Partial<SkillPackage>): Promise<SkillPackage> {
  return request<SkillPackage>("/skills", { method: "POST", body: JSON.stringify(payload) });
}

export function updateSkill(skillId: string, payload: Partial<SkillPackage>): Promise<SkillPackage> {
  return request<SkillPackage>(`/skills/${skillId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function debugSkillDraft(payload: Partial<SkillPackage>): Promise<SkillDebugResult> {
  return request<SkillDebugResult>("/skills/debug", { method: "POST", body: JSON.stringify(payload) });
}

export function debugSkill(skillId: string): Promise<SkillDebugResult> {
  return request<SkillDebugResult>(`/skills/${skillId}/debug`, { method: "POST" });
}

export function listToolConfigs(): Promise<ToolConfig[]> {
  return request<ToolConfig[]>("/tools/configs");
}

export function createToolConfig(payload: Partial<ToolConfig>): Promise<ToolConfig> {
  return request<ToolConfig>("/tools/configs", { method: "POST", body: JSON.stringify(payload) });
}

export function listResourceConfigs(): Promise<ResourceConfig[]> {
  return request<ResourceConfig[]>("/resources/configs");
}

export function createResourceConfig(payload: Partial<ResourceConfig>): Promise<ResourceConfig> {
  return request<ResourceConfig>("/resources/configs", { method: "POST", body: JSON.stringify(payload) });
}

export function listAgentTemplates(): Promise<AgentTemplate[]> {
  return request<AgentTemplate[]>("/agent-templates");
}

export function createAgentTemplate(payload: Partial<AgentTemplate>): Promise<AgentTemplate> {
  return request<AgentTemplate>("/agent-templates", { method: "POST", body: JSON.stringify(payload) });
}

export function listWorkflowTemplates(): Promise<WorkflowTemplate[]> {
  return request<WorkflowTemplate[]>("/workflow-templates");
}

export function createWorkflowTemplate(payload: Partial<WorkflowTemplate>): Promise<WorkflowTemplate> {
  return request<WorkflowTemplate>("/workflow-templates", { method: "POST", body: JSON.stringify(payload) });
}

export function publishWorkflowTemplate(workflowId: string): Promise<WorkflowTemplate> {
  return request<WorkflowTemplate>(`/workflow-templates/${workflowId}/publish`, { method: "POST" });
}

export function cloneWorkflowTemplate(workflowId: string): Promise<WorkflowTemplate> {
  return request<WorkflowTemplate>(`/workflow-templates/${workflowId}/clone`, { method: "POST" });
}
