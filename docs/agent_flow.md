# Agent Flow

The due diligence workflow is intentionally split into generic agent configuration and company-specific run input.

## Agents

| Agent | Purpose | Main Output |
| --- | --- | --- |
| `CoordinatorAgent` | Build the run plan and assign tasks. | Task list and execution plan. |
| `CompanyProfileAgent` | Identify the company profile, leadership, website, products, and ownership hints. | Company profile findings. |
| `WebResearchAgent` | Gather public web, news, announcement, and market references. | Source-backed research findings. |
| `FinancialAnalysisAgent` | Analyze funding, financial signals, operating scale, and business model. | Financial observations and risks. |
| `LegalRiskAgent` | Identify litigation, penalties, sanctions, IP, and compliance risks. | Legal and compliance risk findings. |
| `IndustryAnalysisAgent` | Compare the company with competitors and market dynamics. | Industry position and competitive analysis. |
| `EvidenceVerifierAgent` | Validate evidence coverage, confidence, and conflicts. | Evidence quality summary. |
| `ReportWriterAgent` | Produce the final structured report. | Due diligence report sections. |

## Agent Rules

Every agent must follow these rules:

- Do not invent facts.
- Mark uncertain findings with low confidence.
- Attach evidence IDs to material conclusions.
- Keep conflicting information visible instead of hiding it.
- Return structured JSON that conforms to the shared schema.

## Workflow

Workflow templates are seeded from `agent_service/configs/workflows.yaml` and then managed in the backend configuration catalog. A company project selects one published template through `scope.workflow_template_id`, so the same agent flow can be reused for many companies while different scenarios can choose different agent sequences.

Current templates:

- `standard_due_diligence`: full company, web, financial, legal, industry, verification, and report flow.
- `legal_compliance_due_diligence`: legal/compliance-focused flow.
- `financial_investment_due_diligence`: finance/investment-focused flow.
- `market_entry_due_diligence`: market and competitor-focused flow.

At run time, the backend sends an immutable **workflow snapshot** to the agent service. The snapshot includes the workflow graph, agent templates, Anthropic-style skill packages, executable tools, resource configs, and AgentScope ReAct parameters used by that run.

The agent service writes a **session JSON** for each `POST /runs` (on by default): `agent_service/sessions/<project_id>/<run_id>.json` (override root with `DD_SESSION_HISTORY_DIR`). The file includes `company_config`, `workflow_meta`, `agents_ordered`, an **events** timeline, and on completion the full **`result`** (same data as the HTTP response). Set `DD_SESSION_HISTORY_ENABLED=false` to turn this off. Read-only HTTP: `GET /sessions`, `GET /sessions/{project_id}`, `GET /sessions/{project_id}/{run_id}`.

Each agent template can bind:

- `skill_package_ids`: `SKILL.md` packages that inject procedural guidance and bundled resources into the agent context.
- `tool_ids`: executable tools the agent may call, such as search, web fetch, file reader, vector retrieval, evidence store, and report store.
- `resource_ids`: data resources exposed in the AgentScope ReAct system prompt.
- `react_config`: AgentScope ReAct settings such as `max_iters` and `parallel_tool_calls`.

Skill packages are also synchronized to a fixed project directory at `agent_service/skills/<directory_name>/`. The database remains the configuration catalog, while the project directory keeps the current `SKILL.md` and editable package files visible on disk.

The Agent service builds an AgentScope ReAct runtime for every agent from this snapshot. The runtime creates an AgentScope `Toolkit`, registers the selected tool functions, materializes selected `SKILL.md` packages and package files as AgentScope agent skills, injects bound resources into the ReAct system prompt, and calls the configured real model through an Anthropic Messages-compatible provider.

Default model config:

```json
{
  "baseUrl": "http://127.0.0.1:8081/v1",
  "apiKey": "yuanjun",
  "api": "anthropic-messages",
  "models": [
    {
      "id": "kimi-code",
      "name": "kimi-code(Custom Provider)",
      "reasoning": true,
      "input": ["text", "image"],
      "contextWindow": 128000,
      "maxTokens": 4096
    }
  ]
}
```

When the workflow graph comes from the snapshot rather than YAML defaults alone, coordinator, research agents, verifier, and reporter identifiers may differ while the **overall stage order** (plan, research, analysis, verify, report) stays the same.

```mermaid
flowchart TD
  ProjectConfig[Project_Config] --> WorkflowTemplate[Workflow_Template]
  WorkflowTemplate --> Coordinator[CoordinatorAgent]
  Coordinator --> CompanyProfile[CompanyProfileAgent]
  Coordinator --> WebResearch[WebResearchAgent]
  Coordinator --> Financial[FinancialAnalysisAgent]
  Coordinator --> Legal[LegalRiskAgent]
  Coordinator --> Industry[IndustryAnalysisAgent]
  CompanyProfile --> EvidenceVerifier[EvidenceVerifierAgent]
  WebResearch --> EvidenceVerifier
  Financial --> EvidenceVerifier
  Legal --> EvidenceVerifier
  Industry --> EvidenceVerifier
  EvidenceVerifier --> ReportWriter[ReportWriterAgent]
  ReportWriter --> Report[Structured_Report]
```

## Run observability across services

Runs are intentionally **split across HTTP hops** so the platform API does not block for the duration of LLM-heavy work.

1. **Backend** allocates `run_{random}` (`create_pending_agent_run`), returns **`AgentRunRead`** immediately with **`running`** status.
2. **Agent_service** **`POST /runs`** accepts **`run_id`** in the JSON body when the backend allocates it in advance so the **`RunResult.run_id`** matches the pending row before persistence.
3. **Incremental progress**: after each logical step transitions to **`running`** and again after that step completes the workflow calls **`notify_run_progress`**, which **`POST`**s to **`{PLATFORM_CALLBACK_BASE_URL}/internal/agent-runs/{run_id}/progress`** with header **`X-Agent-Callback-Secret`** (**must equal** **`AGENT_CALLBACK_SECRET`** on the backend). Callback failures are logged only—they **do not abort** the diligence run.

The **frontend workbench polls** the run (`GET /runs/{id}`) and refreshes project evidence while status is `running`, so users see steps and evidence grow when callbacks are enabled.

## Tool Groups

| Tool Group | Purpose |
| --- | --- |
| `search` | Search public web and configured trusted sources. |
| `web_fetch` | Fetch and normalize web page content. |
| `file_reader` | Extract content from uploaded files. |
| `vector_retrieval` | Retrieve relevant chunks from indexed project resources. |
| `evidence_store` | Create and update evidence records. |
| `report_store` | Persist report sections and versions. |

The MVP implements deterministic versions of these tools. Production integrations should keep the same tool names and return compatible schemas.
