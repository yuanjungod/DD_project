# Harness Runtime Storage Guide

`.harness_project/` is the runtime state root for this repository.

Unlike `catalog/` (template baseline), this directory stores mutable engagement/user/session data generated during operation.

Canonical layout: [docs/adr/0003-users-workflows-storage-layout.md](adr/0003-users-workflows-storage-layout.md). Platform rename: [ADR-0008](adr/0008-harness-platform-rename.md).

## Structure

```text
.harness_project/
  engagement_index.json
  users/
    {user_id}/
      workflows/
        {workflow_template_id}/              # user-owned workflow template drafts
          workflow_template.yaml
          agents/
        {workflow_template_id}/
          {engagement_id}/
            meta/
              agent_overrides.json
            shared/
              resources/
                manifest.json
              resource_configs/
                *.yaml
              uploads/
                {file_id}
              skills/
                {directory_name}/...
            sessions/
              {session_id}/
                runs/
                  {run_id}.json
                  outputs/{run_id}_outputs/{step}_{agent}/...
  data/
    platform/
      harness_platform.db
      resource_configs/
        *.yaml
      uploads/
        {file_id}
      uploads_manifest.json
  channels/    # reserved
```

## Semantics

- `users/{user_id}/workflows/{workflow_template_id}/{engagement_id}/meta/agent_overrides.json`
  - Engagement-scoped agent prompt/tool/resource overrides.

- `users/{user_id}/workflows/{workflow_template_id}/{engagement_id}/shared/`
  - Docker-mount-ready engagement resources (resource manifests, uploads, skills, overrides).

- `users/{user_id}/workflows/{workflow_template_id}/{engagement_id}/sessions/{session_id}/runs/`
  - Session-scoped run records and step outputs.
  - One `run_id.json` per run, plus corresponding `outputs/`.

- `users/{user_id}/workflows/{workflow_template_id}/` (template draft only, no `{engagement_id}` sibling)
  - User-owned workflow templates (`workflow_template.yaml` + `agents/`).

- `data/platform/`
  - Platform-level shared runtime data:
    - SQLite DB (`harness_platform.db`; legacy `dd_platform.db` is still read when present)
    - platform resource config overlays
    - platform file-library uploads

## Boundary Rule

- `catalog/` = versioned templates (baseline, mostly static).
- `.harness_project/` = runtime/engagement/user/session state (mutable).

## Migrating from `.dd_project/`

If your workspace still uses legacy **`.dd_project/`**, the platform continues to read it automatically until **`.harness_project/`** exists.

To copy data explicitly:

```bash
python scripts/migrate_dd_project_to_harness_project.py --dry-run
python scripts/migrate_dd_project_to_harness_project.py
```

Use `--merge` when `.harness_project/` already exists and you want to combine trees. The script renames `data/platform/dd_platform.db` to `harness_platform.db` when safe. It does **not** delete `.dd_project/`; remove it manually after verifying the migration.

Set **`HARNESS_DATA_ROOT`** (legacy alias: `DD_DATA_ROOT`) to point at a custom absolute path instead of the repo-root directory.
