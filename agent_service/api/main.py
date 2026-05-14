from __future__ import annotations

from fastapi import FastAPI, HTTPException

from agent_service.agents.agentscope_adapter import initialize_agentscope
from agent_service.api.schemas import RunRequest, RunResult, StepReviewChatRequest, StepReviewChatResponse
from agent_service.session_history import list_session_files, list_session_project_ids, read_session_document
from agent_service.workflows.config_loader import load_agent_config, load_tool_config, load_workflow_config
from agent_service.workflows.due_diligence import DueDiligenceWorkflow


app = FastAPI(title="Due Diligence Agent Service", version="0.1.0")
workflow = DueDiligenceWorkflow()


@app.on_event("startup")
def startup() -> None:
    initialize_agentscope()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config")
def config() -> dict[str, object]:
    agent_config = load_agent_config()
    tool_config = load_tool_config()
    workflow_config = load_workflow_config()
    return {
        "agents": [agent.model_dump() for agent in agent_config.agents],
        "default_workflow_id": workflow_config.default_workflow_id,
        "workflows": [workflow.model_dump() for workflow in workflow_config.workflows],
        "tools": {name: tool.model_dump() for name, tool in tool_config.tools.items()},
    }


@app.post("/runs", response_model=RunResult)
def run_due_diligence(request: RunRequest) -> RunResult:
    try:
        return workflow.run(
            project_id=request.project_id,
            company_config=request.company_config,
            workflow_snapshot=request.workflow_snapshot,
            run_id_override=request.run_id,
            diligence_session_id=request.diligence_session_id,
            attempt_index=request.attempt_index,
            continuation_context=request.continuation_context,
            pause_after_each_step=request.pause_after_each_step,
            resume_from_step_index=request.resume_from_step_index,
            completed_steps=request.completed_steps,
            completed_evidence=request.completed_evidence,
        )
    except ValueError as exc:
        # Invalid snapshot / resume contract / session ids — was surfacing as opaque 500.
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/assist/step-review-chat", response_model=StepReviewChatResponse)
def assist_step_review_chat(request: StepReviewChatRequest) -> StepReviewChatResponse:
    try:
        return workflow.step_review_chat(request)
    except Exception as exc:  # noqa: BLE001 — surface clearer API error
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/sessions/{project_id}/{run_id}")
def get_session_json(project_id: str, run_id: str) -> dict[str, object]:
    try:
        payload = read_session_document(project_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload is None:
        raise HTTPException(status_code=404, detail="Session JSON not found")
    return payload


@app.get("/sessions/{project_id}")
def list_session_entries(project_id: str) -> dict[str, object]:
    try:
        ids = list_session_files(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"project_id": project_id, "run_ids": ids}


@app.get("/sessions")
def list_session_projects() -> dict[str, object]:
    return {"project_ids": list_session_project_ids()}
