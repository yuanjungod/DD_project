# Findings

## Initial Findings
- Workflows/agents have three visible sources: legacy `agent_service/configs/agents.yaml` + `workflows.yaml`, optional migration input `agent_templates.yaml`, and authoritative bundle files under `agent_service/configs/workflow_templates/*.yaml`.
- Normal backend runs build `workflow_snapshot` from file-backed workflow bundles, but `DueDiligenceWorkflow.__init__` still eagerly loads legacy YAML and fallback execution still uses `agents.yaml`/`workflows.yaml`.
- `docs/config_schema.md` previously described `agent_templates.yaml` as authoritative; updated docs now describe it as migration/dev fallback and identify workflow bundles as runtime authority.
- Frontend has `frontend/src/data/workflows.ts` static workflow labels while actual workflow templates are listed from `/workflow-templates`, creating drift when templates are added/renamed.
- Tools and skills are still DB-catalog-backed in snapshots; resources are already file-backed via `catalog/resource_configs` plus data overlay.

## Agent Output Folder Task
- `AgentResult` currently carries `agent/status/summary/findings/evidence` only; no durable output folder address is exposed.
- `DueDiligenceWorkflow.run` keeps prior step outputs in `results` and passes them to `ConfiguredAgentRunner.run`; this is the right place to write a folder after each completed step, then append the result with `output_dir`.
- `AgentScopeReActRuntime._build_task_message` currently injects `previous_agent_results` as summary/findings only; this should include output folder addresses and an explicit `previous_agent_output_folders` list.
- Session history already stores final/partial `RunResult` JSON, so adding `output_dir` to `AgentResult` should be persisted through existing DB JSON fields and callback payloads.
- Implemented folder writer in `agent_service/workflows/agent_outputs.py`; output folders live next to session JSON under `<session_project>/<run_id>_outputs/<step>_<agent>/`.

## App-Level Agent Overrides
- Current `build_workflow_snapshot(db, company_config)` reads only the published workflow bundle and cannot see `project_id`, so it cannot apply per-application Agent prompt/skills/resources overrides.
- Project resources are already project-scoped and merged into `company_config.resources`, but prompt/skills/resource_ids/tool_ids remain template-only.
- Implementation should keep workflow bundle immutable and synthesize overrides into the run snapshot after deep-copying template agents.
