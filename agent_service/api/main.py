from __future__ import annotations

from fastapi import FastAPI, HTTPException

from agent_service.agents.agentscope_adapter import initialize_agentscope
from agent_service.api.schemas import RunRequest, RunResult, StepReviewChatRequest, StepReviewChatResponse
from agent_service.session_history import (
    list_all_session_scenario_ids,
    list_session_files,
    list_session_project_ids,
    list_session_user_ids,
    read_session_document,
)
from agent_service.workflows.config_loader import (
    load_agent_template_catalog,
    load_scenario_template_catalog,
    load_tool_config,
)
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
    tool_config = load_tool_config()
    workflows, default_workflow_id = load_scenario_template_catalog()
    return {
        "agents": load_agent_template_catalog(),
        "default_workflow_id": default_workflow_id,
        "workflows": workflows,
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
            user_id=request.user_id,
            diligence_session_id=request.diligence_session_id,
            attempt_index=request.attempt_index,
            continuation_context=request.continuation_context,
            pause_after_each_step=request.pause_after_each_step,
            resume_from_step_index=request.resume_from_step_index,
            completed_steps=request.completed_steps,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/assist/step-review-chat", response_model=StepReviewChatResponse)
def assist_step_review_chat(request: StepReviewChatRequest) -> StepReviewChatResponse:
    try:
        return workflow.step_review_chat(request)
    except Exception as exc:  # noqa: BLE001 — surface clearer API error
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/sessions/{scenario_id}/{user_id}/{project_id}/{run_id}")
def get_session_json(scenario_id: str, user_id: str, project_id: str, run_id: str) -> dict[str, object]:
    try:
        payload = read_session_document(scenario_id, user_id, project_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload is None:
        raise HTTPException(status_code=404, detail="Session JSON not found")
    return payload


@app.get("/sessions/{scenario_id}/{user_id}/{project_id}")
def list_session_entries(scenario_id: str, user_id: str, project_id: str) -> dict[str, object]:
    try:
        ids = list_session_files(scenario_id, user_id, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"scenario_id": scenario_id, "user_id": user_id, "project_id": project_id, "run_ids": ids}


@app.get("/sessions/{scenario_id}/{user_id}")
def list_session_projects(scenario_id: str, user_id: str) -> dict[str, object]:
    try:
        ids = list_session_project_ids(scenario_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"scenario_id": scenario_id, "user_id": user_id, "project_ids": ids}


@app.get("/sessions/{scenario_id}")
def list_session_users(scenario_id: str) -> dict[str, object]:
    try:
        ids = list_session_user_ids(scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"scenario_id": scenario_id, "user_ids": ids}


@app.get("/sessions")
def list_session_scenarios() -> dict[str, object]:
    return {"scenario_ids": list_all_session_scenario_ids()}
