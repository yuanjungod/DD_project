# ADR-0003: `.harness_project/users/workflows/` storage layout

## Status

Accepted

> **Note:** This ADR was written when the runtime root was named `.dd_project/`. Current code uses **`.harness_project/`** with the same tree shape below.

## Context

Earlier documentation described engagement state under `.dd_project/projects/{engagement_id}/`. Runtime code resolves paths via `engagement_index.json` and the tree:

`.harness_project/users/{user_id}/workflows/{workflow_template_id}/{engagement_id}/`

## Decision

Canonical layout:

```text
.harness_project/
  engagement_index.json
  users/
    {user_id}/
      workflows/
        {workflow_template_id}/          # user-owned workflow template drafts
          workflow_template.yaml
          agents/
        {workflow_template_id}/
          {engagement_id}/                # engagement runtime home
            meta/agent_overrides.json
            shared/{resources,uploads,skills,resource_configs}/
            sessions/{session_id}/runs/
              {run_id}.json
              outputs/
                {run_id}_outputs/
                  {run_id}_step_{NNN}_{agent_name}/   # one folder per agent step
                    README.md
                    …                                 # agent-written artifacts
  data/platform/                          # SQLite, platform overlays, library uploads
  channels/                               # reserved
```

The legacy `.dd_project/projects/` tree and repo-root `.dd_project/users/...` paths are **not** read by current code (migrate with `scripts/migrate_dd_project_to_harness_project.py`).

## Consequences

- All documentation and examples must use the canonical path above.
- `register_engagement_tree()` in `backend/app/services/fs_layout.py` maintains `engagement_index.json` for lookup.
- Agent session JSON and step outputs live under the engagement `sessions/` branch.
