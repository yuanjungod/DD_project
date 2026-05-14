# Progress

## 2026-05-14
- Started cleanup task focused on file-backed configuration and resource sources.
- Implemented lazy legacy YAML loading in agent workflow runtime.
- Added file-backed loaders/sync for skill packages and tool configs.
- Removed unused `SkillConfig` ORM model/export.
- Reworked frontend workflow display names to come from API templates instead of static IDs.
- Updated docs and legacy YAML comments to clarify bundle/file-backed authority.
- Verification: Python syntax check passed; frontend `npx tsc --noEmit` passed; IDE lints clean.
- Added per-agent handoff folders under the session tree: each completed step now writes README.md, result.json, findings, and evidence resource files, then stores output_dir/output_readme_path on AgentResult.
- Added `agent_output_reader` as an automatic runtime tool so downstream agents can read prior handoff folders by folder_path.
- Added backend read API and ProjectDetail UI panel to show each completed Agent output folder during scenario execution.
- Simplified ProjectDetail execution area: removed evidence/report cards from the page and focused the main panel on per-step Agent output folders.
- Changed output folder UI to show a clickable file index first; file content is shown only after selection. Moved step review chat into the matching paused Agent step.
- Removed Agent-level output contract type (`output_schema`) from agent DTOs, snapshots, workflow bundles, legacy agent YAML, and frontend Agent template UI. Agent output requirements now live in prompts/Skills.
- Started app-level Agent override implementation: goal is per-project overlay for prompt/skills/tools/resources/file scope that only affects future run snapshots.
- Added project Agent override manifest/API under each project, wired snapshot synthesis to apply overrides without mutating workflow bundles, and exposed per-Agent override editors in the application resources page.
- Verification: changed backend files compile with `.venv/bin/python -m py_compile`; frontend `npm run build` passes.
- Removed aggregate `evidence` and `report` from agent_service `RunResult`; workflow no longer synthesizes a final report object, leaving final content in per-Agent output folders and file handoffs.
