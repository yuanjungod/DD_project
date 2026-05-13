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
