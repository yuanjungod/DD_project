# ADR-0003: `.dd_project/users/workflows/` storage layout

## Status

Accepted (2026-05-29)

## Context

Earlier documentation described engagement state under `.dd_project/projects/{engagement_id}/`. Runtime code resolves paths via `engagement_index.json` and the tree:

`.dd_project/users/{user_id}/workflows/{workflow_template_id}/{engagement_id}/`

## Decision

Canonical layout:

```text
.dd_project/
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
            sessions/{session_id}/runs/{workflow_template_id}/
  data/platform/                          # SQLite, platform overlays, library uploads
  channels/                               # reserved
```

The legacy `.dd_project/projects/` tree is **not** used by current code.

## Consequences

- All documentation and examples must use the canonical path above.
- `register_engagement_tree()` in `backend/app/services/fs_layout.py` maintains `engagement_index.json` for lookup.
- Agent session JSON and step outputs live under the engagement `sessions/` branch.
