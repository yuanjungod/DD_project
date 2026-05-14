import type {
  AgentRun,
  AgentStepOutputFolder,
  AgentTemplate,
  AuthSession,
  CompanyConfig,
  DiligenceSessionModel,
  Evidence,
  Project,
  ProjectAgentOverride,
  Report,
  Resource,
  ResourceConfig,
  LibraryFile,
  Scenario,
  SkillDebugResult,
  SkillPackage,
  StepReviewChatApiResponse,
  StepReviewChatTurn,
  ToolConfig,
  User,
  WorkflowTemplate,
} from "../types/domain";

const configured = import.meta.env.VITE_API_BASE_URL;
export const API_BASE_URL =
  typeof configured === "string" && configured.trim() !== ""
    ? configured.trim()
    : import.meta.env.DEV
      ? "/api"
      : "http://127.0.0.1:8010";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem("dd_access_token");
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options?.headers ?? {}),
      },
      ...options,
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg === "Failed to fetch" || msg.includes("NetworkError")) {
      throw new Error(
        `无法连接 API（当前基址：${API_BASE_URL}）。请确认 Backend 已在 127.0.0.1:8010 运行，并使用 npm run dev 开发服务器（带 /api 代理）。`,
      );
    }
    throw err;
  }

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

export function createProject(payload: {
  name: string;
  company_config: CompanyConfig;
  initial_resources?: Array<{ type: string; value: string; metadata_json?: Record<string, unknown> }>;
}): Promise<Project> {
  return request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deleteProject(projectId: string): Promise<void> {
  const token = localStorage.getItem("dd_access_token");
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}`, {
      method: "DELETE",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg === "Failed to fetch" || msg.includes("NetworkError")) {
      throw new Error(
        `无法连接 API（当前基址：${API_BASE_URL}）。请确认 Backend 已在 127.0.0.1:8010 运行，并使用 npm run dev 开发服务器（带 /api 代理）。`,
      );
    }
    throw err;
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `删除失败（${response.status}）`);
  }
}

export function listResources(projectId: string): Promise<Resource[]> {
  return request<Resource[]>(`/projects/${projectId}/resources`);
}

export function listProjectAgentOverrides(projectId: string): Promise<ProjectAgentOverride[]> {
  return request<ProjectAgentOverride[]>(`/projects/${encodeURIComponent(projectId)}/agent-overrides`);
}

export function upsertProjectAgentOverride(
  projectId: string,
  agentId: string,
  payload: ProjectAgentOverride,
): Promise<ProjectAgentOverride> {
  return request<ProjectAgentOverride>(
    `/projects/${encodeURIComponent(projectId)}/agent-overrides/${encodeURIComponent(agentId)}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
}

export async function deleteProjectAgentOverride(projectId: string, agentId: string): Promise<void> {
  const token = localStorage.getItem("dd_access_token");
  const response = await fetch(
    `${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/agent-overrides/${encodeURIComponent(agentId)}`,
    {
      method: "DELETE",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    },
  );
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `删除失败（${response.status}）`);
  }
}

export function createResource(
  projectId: string,
  payload: { type: string; value: string; metadata_json?: Record<string, unknown> },
): Promise<Resource> {
  return request<Resource>(`/projects/${encodeURIComponent(projectId)}/resources`, {
    method: "POST",
    body: JSON.stringify({
      type: payload.type,
      value: payload.value,
      metadata_json: payload.metadata_json ?? {},
    }),
  });
}

export async function deleteResource(projectId: string, resourceId: string): Promise<void> {
  const token = localStorage.getItem("dd_access_token");
  const response = await fetch(
    `${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/resources/${encodeURIComponent(resourceId)}`,
    {
      method: "DELETE",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    },
  );
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `删除失败（${response.status}）`);
  }
}

export async function uploadProjectFile(projectId: string, file: File): Promise<Resource> {
  const token = localStorage.getItem("dd_access_token");
  const formData = new FormData();
  formData.append("file", file);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/uploads`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg === "Failed to fetch" || msg.includes("NetworkError")) {
      throw new Error(
        `无法连接 API（当前基址：${API_BASE_URL}）。请确认 Backend 已在 127.0.0.1:8010 运行，并使用 npm run dev 开发服务器（带 /api 代理）。`,
      );
    }
    throw err;
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `上传失败（${response.status}）`);
  }
  return response.json() as Promise<Resource>;
}

export function listLibraryUploads(): Promise<LibraryFile[]> {
  return request<LibraryFile[]>("/library/uploads");
}

export async function uploadLibraryFile(file: File): Promise<LibraryFile> {
  const token = localStorage.getItem("dd_access_token");
  const formData = new FormData();
  formData.append("file", file);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/library/uploads`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg === "Failed to fetch" || msg.includes("NetworkError")) {
      throw new Error(
        `无法连接 API（当前基址：${API_BASE_URL}）。请确认 Backend 已在 127.0.0.1:8010 运行，并使用 npm run dev 开发服务器（带 /api 代理）。`,
      );
    }
    throw err;
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `上传失败（${response.status}）`);
  }
  return response.json() as Promise<LibraryFile>;
}

export async function deleteLibraryUpload(fileId: string): Promise<void> {
  const token = localStorage.getItem("dd_access_token");
  const response = await fetch(`${API_BASE_URL}/library/uploads/${encodeURIComponent(fileId)}`, {
    method: "DELETE",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `删除失败（${response.status}）`);
  }
}

export function listDiligenceSessions(projectId: string): Promise<DiligenceSessionModel[]> {
  return request<DiligenceSessionModel[]>(`/projects/${encodeURIComponent(projectId)}/diligence-sessions`);
}

export function startRun(
  projectId: string,
  body: {
    session_mode?: "new" | "continue";
    diligence_session_id?: string | null;
    interaction_mode?: "batch" | "step_gated";
  } = {},
): Promise<AgentRun> {
  return request<AgentRun>(`/projects/${encodeURIComponent(projectId)}/runs`, {
    method: "POST",
    body: JSON.stringify(body ?? {}),
  });
}

export function continueStepGated(runId: string): Promise<AgentRun> {
  return request<AgentRun>(`/runs/${encodeURIComponent(runId)}/continue-step-gated`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function postStepReviewChat(runId: string, stepId: string, message: string): Promise<StepReviewChatApiResponse> {
  return request<StepReviewChatApiResponse>(
    `/runs/${encodeURIComponent(runId)}/steps/${encodeURIComponent(stepId)}/review-chat`,
    {
      method: "POST",
      body: JSON.stringify({ message }),
    },
  );
}

export function listStepReviewChatTurns(runId: string, stepId: string): Promise<StepReviewChatTurn[]> {
  return request<StepReviewChatTurn[]>(
    `/runs/${encodeURIComponent(runId)}/steps/${encodeURIComponent(stepId)}/review-chat-turns`,
  );
}

export function getAgentStepOutputFolder(runId: string, stepId: string): Promise<AgentStepOutputFolder> {
  return request<AgentStepOutputFolder>(
    `/runs/${encodeURIComponent(runId)}/steps/${encodeURIComponent(stepId)}/output-folder`,
  );
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

export async function importSkillZip(file: File, directoryName?: string): Promise<SkillPackage> {
  const token = localStorage.getItem("dd_access_token");
  const formData = new FormData();
  formData.append("file", file);
  if (directoryName?.trim()) {
    formData.append("directory_name", directoryName.trim());
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/skills/import-zip`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg === "Failed to fetch" || msg.includes("NetworkError")) {
      throw new Error(
        `无法连接 API（当前基址：${API_BASE_URL}）。请确认 Backend 已在 127.0.0.1:8010 运行，并使用 npm run dev 开发服务器（带 /api 代理）。`,
      );
    }
    throw err;
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `上传失败（${response.status}）`);
  }
  return response.json() as Promise<SkillPackage>;
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

export function updateResourceConfig(
  resourceId: string,
  payload: Partial<Pick<ResourceConfig, "name" | "description" | "type" | "connection_config" | "enabled">>,
): Promise<ResourceConfig> {
  return request<ResourceConfig>(`/resources/configs/${encodeURIComponent(resourceId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteResourceConfig(resourceId: string): Promise<void> {
  const token = localStorage.getItem("dd_access_token");
  const response = await fetch(`${API_BASE_URL}/resources/configs/${encodeURIComponent(resourceId)}`, {
    method: "DELETE",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `删除失败（${response.status}）`);
  }
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

export async function deleteWorkflowTemplate(workflowId: string): Promise<void> {
  const token = localStorage.getItem("dd_access_token");
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/workflow-templates/${encodeURIComponent(workflowId)}`, {
      method: "DELETE",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg === "Failed to fetch" || msg.includes("NetworkError")) {
      throw new Error(
        `无法连接 API（当前基址：${API_BASE_URL}）。请确认 Backend 已在 127.0.0.1:8010 运行，并使用 npm run dev 开发服务器（带 /api 代理）。`,
      );
    }
    throw err;
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `删除失败（${response.status}）`);
  }
}
