# ADR-0004: Report derived from agent step outputs

## Status

Accepted (2026-05-29)

## Context

The database and API expose a `Report` entity. The agent workflow produces per-step handoff folders (at minimum platform-managed `README.md`; agents may add other files such as optional `result.json`) but does not return a top-level `report` field in `RunResult`.

## Decision

For MVP, **structured reports are derived from the final agent step output** (typically `ReportWriterAgent`) rather than requiring a separate `report` payload in the agent HTTP response.

- When `result["report"]` is present (future agent versions), persist it as today.
- When absent, synthesize a minimal report from the last completed step's `result.json` / README metadata if available.
- The UI continues to show per-step output folders as the primary review surface.

## Consequences

- `persistence.py` gains a fallback report builder.
- Full structured report schema evolution can proceed independently of agent `RunResult` shape.
- Option to restore explicit agent-produced reports later without breaking existing runs.
