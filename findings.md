# Findings

## Initial Findings
- Workflows/agents have three visible sources: legacy `agent_service/configs/agents.yaml` + `workflows.yaml`, optional migration input `agent_templates.yaml`, and authoritative bundle files under `agent_service/configs/workflow_templates/*.yaml`.
- Normal backend runs build `workflow_snapshot` from file-backed workflow bundles, but `DueDiligenceWorkflow.__init__` still eagerly loads legacy YAML and fallback execution still uses `agents.yaml`/`workflows.yaml`.
- `docs/config_schema.md` previously described `agent_templates.yaml` as authoritative; updated docs now describe it as migration/dev fallback and identify workflow bundles as runtime authority.
- Frontend has `frontend/src/data/workflows.ts` static workflow labels while actual workflow templates are listed from `/workflow-templates`, creating drift when templates are added/renamed.
- Tools and skills are still DB-catalog-backed in snapshots; resources are already file-backed via `catalog/resource_configs` plus data overlay.
