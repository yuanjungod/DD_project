# Shared JSON Schemas

Cross-service contracts live under `shared/schemas/`. Backend, agent_service, and frontend should align with these files when evolving run payloads.

| Schema | Purpose |
| --- | --- |
| [company_config.schema.json](company_config.schema.json) | Engagement company configuration |
| [workflow_snapshot.schema.json](workflow_snapshot.schema.json) | Immutable run bundle from backend |
| [run_request.schema.json](run_request.schema.json) | `POST /runs` body to agent_service |
| [run_result.schema.json](run_result.schema.json) | Agent HTTP response / backend finalize payload |
| [agent_result.schema.json](agent_result.schema.json) | Per-step agent output |
| [report.schema.json](report.schema.json) | Structured diligence report |

Python services may continue to use Pydantic models; these JSON schemas are the portable contract reference. When fields change, update the schema first, then mirror in `backend/app/schemas/dto.py`, `agent_service/api/schemas.py`, and `frontend/src/types/domain.ts`.

See [ADR-0004](../../docs/adr/0004-report-from-step-outputs.md) for report synthesis when `report` is omitted from `RunResult`.
