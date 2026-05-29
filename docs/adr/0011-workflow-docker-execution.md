# ADR-0011: Per-workflow Docker command execution

## Status

Accepted

## Context

Harness runs `agent_service` on the host. Agents use AgentScope built-ins (`execute_shell_command`, `execute_python_code`, `view_text_file`) which execute in the agent process. Operators want optional isolation: per user and workflow template, run commands and file I/O inside a lightweight Docker container while keeping LLM calls on the host.

## Decision

- Add `workflow.runtime.command_execution`: `host` (default) or `docker`.
- One long-lived container per **`user_id` + `workflow_template_id`**, named `harness-exec-{user}-{template}`.
- **Idle auto-stop:** if no command/file activity for `workflow.runtime.docker.idle_ttl_seconds` (default **1200** = 20 minutes), `agent_service` stops the container. A background sweeper runs every 60s; activity is also checked on each `ensure_container` / `docker exec`.
- Bind mount only the workflow tree:  
  `.harness_project/users/{user_id}/workflows/{workflow_template_id}` → `/workspace/workflow`.
- Image **`harness-exec:0.1.0`** (`docker/harness-exec/Dockerfile`): Python 3.12 slim + bash/coreutils; no AgentScope/LLM.
- Host `agent_service` uses the **Docker CLI** (`docker run` / `docker exec`; no Python `docker` SDK required) for shell, Python, and file reads under the mount.
- `ReActAgent` and model calls remain on the host; only the three builtins are wrapped in docker mode.
- Catalog `ToolRegistry` tools stay on the host in phase 1.

## Consequences

- `agent_service` needs access to `/var/run/docker.sock` when docker mode is used.
- Prompts and handoff paths use **container paths** (`/workspace/workflow/...`) in docker mode so the model writes paths valid inside the container.
- Missing `harness-exec` image fails fast with build script hint.

## References

- [docs/harness_runtime_storage.md](../harness_runtime_storage.md)
- [ADR-0006](0006-docker-shared-filesystem.md)
