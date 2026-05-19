# Findings

## Initial Findings
- Workflow/scenario and Agent definitions are separated: scenario graphs live under `agent_service/configs/scenario_templates/*.yaml`, reusable Agent definitions live in `agent_service/configs/agent_templates.yaml`.
- Normal backend runs and agent_service execution both require a `workflow_snapshot` built from the published scenario file plus the agent catalog.
- Frontend has `frontend/src/data/workflows.ts` static workflow labels while actual workflow templates are listed from `/workflow-templates`, creating drift when templates are added/renamed.
- Tools and skills are still DB-catalog-backed in snapshots; resources are already file-backed via `catalog/resource_configs` plus data overlay.

## Agent Output Folder Task
- `AgentResult` carries `agent/status/summary/findings` plus `output_dir` / `output_readme_path` for per-step handoff folders.
- `DueDiligenceWorkflow.run` keeps prior step outputs in `results` and passes them to `ConfiguredAgentRunner.run`; this is the right place to write a folder after each completed step, then append the result with `output_dir`.
- `AgentScopeReActRuntime._build_task_message` currently injects `previous_agent_results` as summary/findings only; this should include output folder addresses and an explicit `previous_agent_output_folders` list.
- Session history already stores final/partial `RunResult` JSON, so adding `output_dir` to `AgentResult` should be persisted through existing DB JSON fields and callback payloads.
- Implemented folder writer in `agent_service/workflows/agent_outputs.py`; output folders live next to session JSON under `<session_project>/<run_id>_outputs/<step>_<agent>/`.

## App-Level Agent Overrides
- Earlier `build_workflow_snapshot(db, company_config)` read only the published workflow template and could not see `project_id`, so it could not apply per-application Agent prompt/skills/resources overrides.
- Project resources are already project-scoped and merged into `company_config.resources`, but prompt/skills/resource_ids/tool_ids remain template-only.
- Implementation keeps scenario and global Agent templates immutable and synthesizes overrides into the run snapshot after deep-copying template agents.

## Runtime Paths and Users Cleanup
- Backend writable file resources already resolve through `backend/app/services/fs_layout.py` using `filesystem_data_root` (default `data/dd_store`), but `DATABASE_URL` still defaults to `sqlite:///./dd_platform.db`, so the SQLite file changes location depending on the backend working directory.
- Agent session history defaults to `agent_service/sessions`, while backend project/resource/uploads already live under `data/dd_store`; completed agent output folders are written next to the session JSON, so this splits runtime data across two trees.
- Default dev users are hardcoded in `backend/app/core/auth.py`; moving them to a small file-backed catalog keeps user seed data visible and editable without changing auth behavior.
- Implemented cleanup keeps explicit env overrides intact: `DATABASE_URL` still wins, `DD_SESSION_HISTORY_DIR` still wins for agent sessions, and `DD_DEFAULT_USERS_CONFIG` can point at another user seed file.
- Session config/runtime state is separate from both scenario and Agent catalogs: agent-service session JSON and per-step output folders default to `DD_DATA_ROOT/agent_service/sessions`.
