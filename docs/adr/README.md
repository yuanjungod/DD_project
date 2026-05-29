# Architecture Decision Records

Index of significant design decisions for DD_project.

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-file-backed-skill-tool-catalog.md) | File-backed skill and tool catalog (no DB mirror) | Accepted |
| [0002](0002-engagement-terminology.md) | Engagement vs Project naming | Accepted |
| [0003](0003-users-workflows-storage-layout.md) | `.dd_project/users/workflows/` storage layout | Accepted |
| [0004](0004-report-from-step-outputs.md) | Report derived from agent step outputs | Accepted |
| [0005](0005-linear-workflow-graph.md) | Linear workflow graph execution (MVP) | Accepted |
| [0006](0006-docker-shared-filesystem.md) | Single-node Docker with shared filesystem | Accepted |
| [0007](0007-engagement-api-project-db.md) | Engagement in API, Project in database | Accepted |

## Template

When adding a new ADR, copy this structure:

```markdown
# ADR-NNNN: Title

## Status

Proposed | Accepted | Deprecated

## Context

What problem or constraint led to this decision?

## Decision

What we chose and why.

## Consequences

Positive, negative, and follow-up work.
```
