export type CompanyConfig = {
  target_company: {
    name: string;
    aliases: string[];
  };
  workflow_template_id: string;
  workflow_template_version?: number | null;
  resources: {
    uploaded_files: string[];
    trusted_sources: string[];
    blocked_sources: string[];
    competitors: string[];
    metrics?: Record<string, unknown>[];
    external_clues?: Record<string, unknown>[];
    agent_resource_scopes?: Record<string, unknown>[];
  };
};

export type InstanceConfig = {
  workflow_template_id: string;
  workflow_template_version?: number | null;
  resources: CompanyConfig["resources"];
  extensions?: {
    due_diligence?: { target_company?: CompanyConfig["target_company"] };
    subject?: { name: string; aliases?: string[]; kind?: string };
    workflow_task?: { description?: string; task?: string; goal?: string };
    [key: string]: unknown;
  };
  /** @deprecated Legacy due-diligence root field */
  target_company?: CompanyConfig["target_company"];
};

export type Engagement = {
  id: string;
  name: string;
  company_key: string;
  application_id: string;
  version: number;
  instance_config: InstanceConfig;
  /** @deprecated Use instance_config */
  company_config: CompanyConfig;
  created_at: string;
  updated_at: string;
};

export type Resource = {
  id: string;
  engagement_id: string;
  type: string;
  value: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type EngagementAgentOverride = {
  agent_id: string;
  prompt_append: string;
  prompt_override: string;
  skill_package_ids_add: string[];
  skill_package_ids_remove: string[];
  tool_ids_add: string[];
  tool_ids_remove: string[];
  resource_ids_add: string[];
  resource_ids_remove: string[];
  platform_upload_file_ids: string[];
  react_config_override: Record<string, unknown>;
  enabled: boolean;
  updated_at?: string | null;
};

export type AgentStep = {
  id: string;
  run_id: string;
  agent: string;
  status: string;
  summary: string;
  result: Record<string, unknown>;
};

export type AgentStepOutputFile = {
  path: string;
  name: string;
  size_bytes: number;
  content_type: "text" | "binary";
  content?: string;
  truncated?: boolean;
  preview_unavailable?: boolean;
};

export type AgentStepOutputFolder = {
  available: boolean;
  step_id: string;
  agent: string;
  folder_path?: string;
  readme_path?: string;
  readme?: string;
  files?: AgentStepOutputFile[];
  reason?: string;
};

export type Report = {
  id: string;
  engagement_id: string;
  run_id: string;
  title: string;
  executive_summary: string;
  overall_risk: string;
  sections: Array<{
    title: string;
    summary: string;
    risk_level: string;
  }>;
  created_at: string;
};

export type StepReviewChatTurn = {
  id: string;
  step_id: string;
  role: string;
  content: string;
  created_at: string;
};

export type StepReviewChatApiResponse = {
  reply: string;
  turns: StepReviewChatTurn[];
};

export type AgentRun = {
  id: string;
  engagement_id: string;
  session_id?: string | null;
  attempt_index?: number | null;
  status: string;
  started_at: string;
  completed_at?: string | null;
  raw_result: Record<string, unknown>;
  steps: AgentStep[];
  report?: Report | null;
};

export type AgentRunBrief = {
  id: string;
  engagement_id: string;
  status: string;
  attempt_index?: number | null;
  session_id?: string | null;
  started_at: string;
};

export type WorkflowSessionModel = {
  id: string;
  engagement_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  runs: AgentRunBrief[];
};

/** @deprecated Use WorkflowSessionModel */
export type DiligenceSessionModel = WorkflowSessionModel;

export type User = {
  id: string;
  email: string;
  name: string;
  role: "admin" | "analyst" | "viewer";
  created_at: string;
};

export type AuthSession = {
  access_token: string;
  token_type: "bearer";
  user: User;
};

export type PublishedWorkflowTemplate = {
  id: string;
  name: string;
  description: string;
  workflow_template: string;
  agents: string[];
};

export type SkillPackage = {
  id: string;
  name: string;
  description: string;
  directory_name: string;
  skill_md: string;
  package_files: Record<string, string>;
  resources_manifest: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type SkillDebugResult = {
  valid: boolean;
  checks: string[];
  metadata: Record<string, unknown>;
  agent_skill_prompt?: string | null;
  errors: string[];
};

export type ToolConfig = {
  id: string;
  name: string;
  description: string;
  implementation: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  requires_api_key: boolean;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

/** Platform-shared upload (merged into every run's resources.uploaded_files). */
export type LibraryFile = {
  id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
};

export type ResourceConfig = {
  id: string;
  name: string;
  type: string;
  description: string;
  connection_config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  /** Overlay YAML exists under data store; DELETE removes overlay file. */
  deletable?: boolean;
  /** Repo catalog defines this id (may still have overlay override). */
  builtin_base?: boolean;
};

export type AgentTemplate = {
  id: string;
  name: string;
  role: string;
  prompt: string;
  sub_agent_ids?: string[];
  skill_package_ids: string[];
  tool_ids: string[];
  resource_ids: string[];
  /** Empty = use all merged uploaded_files at run time; otherwise restrict agent-visible upload file IDs. */
  platform_upload_file_ids?: string[];
  react_config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type WorkflowGraph = {
  nodes: Array<{
    id: string;
    agent_template_id: string;
    /** Optional sub-agents executed after node master agent. */
    sub_agent_template_ids?: string[];
    stage?: string;
    position?: { x: number; y: number };
    width?: number;
    height?: number;
  }>;
  edges: Array<{ from: string; to: string }>;
  entry_node: string;
  report_node: string;
};

export type WorkflowTemplate = {
  id: string;
  name: string;
  description: string;
  workflow_template: string;
  graph: WorkflowGraph;
  status: "draft" | "published";
  version: number;
  created_at: string;
  updated_at: string;
};
