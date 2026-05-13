export type CompanyConfig = {
  target_company: {
    name: string;
    aliases: string[];
    website: string;
    jurisdiction: string;
    industry: string;
    keywords: string[];
  };
  scope: {
    workflow_id: string;
    workflow_template_id?: string | null;
    workflow_template_version?: number | null;
    scenario: string;
    time_range: string;
    focus_areas: string[];
    report_language: string;
  };
  resources: {
    uploaded_files: string[];
    trusted_sources: string[];
    blocked_sources: string[];
    competitors: string[];
  };
};

export type Project = {
  id: string;
  name: string;
  company_config: CompanyConfig;
  created_at: string;
  updated_at: string;
};

export type Resource = {
  id: string;
  project_id: string;
  type: string;
  value: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type AgentStep = {
  id: string;
  run_id: string;
  agent: string;
  status: string;
  summary: string;
  result: Record<string, unknown>;
};

export type Evidence = {
  id: string;
  run_id: string;
  project_id: string;
  title: string;
  source_type: string;
  source_url?: string | null;
  file_id?: string | null;
  excerpt: string;
  confidence: number;
  collected_by: string;
  metadata_json: Record<string, unknown>;
};

export type Report = {
  id: string;
  project_id: string;
  run_id: string;
  title: string;
  executive_summary: string;
  overall_risk: string;
  sections: Array<{
    title: string;
    summary: string;
    risk_level: string;
    evidence_ids: string[];
  }>;
  created_at: string;
};

export type AgentRun = {
  id: string;
  project_id: string;
  status: string;
  started_at: string;
  completed_at?: string | null;
  raw_result: Record<string, unknown>;
  steps: AgentStep[];
  evidence: Evidence[];
  report?: Report | null;
};

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

export type Scenario = {
  id: string;
  name: string;
  description: string;
  scenario: string;
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

export type ResourceConfig = {
  id: string;
  name: string;
  type: string;
  description: string;
  connection_config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type AgentTemplate = {
  id: string;
  name: string;
  role: string;
  prompt: string;
  skill_package_ids: string[];
  tool_ids: string[];
  skill_ids: string[];
  resource_ids: string[];
  react_config: Record<string, unknown>;
  output_schema: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type WorkflowGraph = {
  nodes: Array<{ id: string; agent_template_id: string; stage?: string }>;
  edges: Array<{ from: string; to: string }>;
  entry_node: string;
  report_node: string;
};

export type WorkflowTemplate = {
  id: string;
  name: string;
  description: string;
  scenario: string;
  graph: WorkflowGraph;
  status: "draft" | "published";
  version: number;
  created_at: string;
  updated_at: string;
};
