# Catalog Directory Guide

`catalog/` stores built-in, repo-versioned templates and seed files.

It is the "baseline template layer" of the system:

- Keep stable defaults here.
- Track changes with Git review.
- Do not store runtime state here.

## Structure

```text
catalog/
  README.md
  default_users.yaml
  agents/
    {agent_id}.yaml
  workflow_templates/
    {workflow_template_id}/
      workflow_template.yaml
      agents/
        {agent_id}.yaml
  resource_configs/
    {resource_id}.yaml
```

## Files And Folders

### `default_users.yaml`

Development seed users loaded by backend startup when the users table is empty.

Typical content:

- login email
- display name
- role
- default password (for local/dev only)

### `agents/`

Global agent template library.

Each file is one reusable agent template (`{agent_id}.yaml`), for example:

- role
- prompt
- tools/resources/skills binding
- model react config
- `enabled` status

These files are managed by the Agent Templates admin APIs/UI and used as source templates.

### `workflow_templates/`

Built-in workflow templates.

Each workflow template directory represents one workflow template:

- `workflow_template.yaml`: workflow metadata and graph (`nodes`, `edges`, `entry_node`, `report_node`)
- `agents/`: agent definitions referenced by this workflow template

Important boundary:

- This folder is template configuration only.
- Runtime runs/outputs are stored under `.harness_project/users/{user_id}/workflows/{workflow_template_id}/{engagement_id}/sessions/{session_id}/runs/`, not here.

### `resource_configs/`

Built-in platform resource connector definitions.

Examples include public web, file store, database-like connectors, etc.

Runtime/project overlays are stored under `.harness_project/data/platform/resource_configs` (or the configured data root), not in this folder.

## Ownership And Update Rules

- Product/dev baseline changes: edit under `catalog/` and commit to Git.
- Runtime/project/user state: write under `.harness_project/`.
- Avoid mixing template files and runtime artifacts in the same path.

