from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException

from agent_service.agents.agentscope_adapter import initialize_agentscope
from agent_service.api.auth import require_agent_api_key
from agent_service.api.schemas import RunRequest, RunResult, StepReviewChatRequest, StepReviewChatResponse
from agent_service.session_history import (
    list_all_session_workflow_template_ids,
    list_session_files,
    list_session_engagement_ids,
    list_session_user_ids,
    read_session_document,
)
from agent_service.workflows.config_loader import (
    load_agent_template_catalog,
    load_workflow_template_catalog,
    load_tool_config,
)
from agent_service.workflows.workflow_engine import WorkflowEngine


app = FastAPI(title="Harness Agent Service", version="0.1.0")
workflow = WorkflowEngine()
_require_agent_key = [Depends(require_agent_api_key)]


@app.on_event("startup")
def startup() -> None:
    initialize_agentscope()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config", dependencies=_require_agent_key)
def config() -> dict[str, object]:
    tool_config = load_tool_config()
    workflows, default_workflow_id = load_workflow_template_catalog()
    return {
        "agents": load_agent_template_catalog(),
        "default_workflow_id": default_workflow_id,
        "workflows": workflows,
        "tools": {name: tool.model_dump() for name, tool in tool_config.tools.items()},
    }


@app.post("/runs", response_model=RunResult, dependencies=_require_agent_key)
def run_workflow(request: RunRequest) -> RunResult:
    try:
        return workflow.run(
            engagement_id=request.engagement_id,
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


@app.post("/assist/step-review-chat", response_model=StepReviewChatResponse, dependencies=_require_agent_key)
def assist_step_review_chat(request: StepReviewChatRequest) -> StepReviewChatResponse:
    try:
        return workflow.step_review_chat(request)
    except Exception as exc:  # noqa: BLE001 — surface clearer API error
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/sessions/{workflow_template_id}/{user_id}/{engagement_id}/{run_id}", dependencies=_require_agent_key)
def get_session_json(workflow_template_id: str, user_id: str, engagement_id: str, run_id: str) -> dict[str, object]:
    try:
        payload = read_session_document(workflow_template_id, user_id, engagement_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload is None:
        raise HTTPException(status_code=404, detail="Session JSON not found")
    return payload


@app.get("/sessions/{workflow_template_id}/{user_id}/{engagement_id}", dependencies=_require_agent_key)
def list_session_entries(workflow_template_id: str, user_id: str, engagement_id: str) -> dict[str, object]:
    try:
        ids = list_session_files(workflow_template_id, user_id, engagement_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "workflow_template_id": workflow_template_id,
        "user_id": user_id,
        "engagement_id": engagement_id,
        "run_ids": ids,
    }


@app.get("/sessions/{workflow_template_id}/{user_id}", dependencies=_require_agent_key)
def list_session_engagements(workflow_template_id: str, user_id: str) -> dict[str, object]:
    try:
        ids = list_session_engagement_ids(workflow_template_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"workflow_template_id": workflow_template_id, "user_id": user_id, "engagement_ids": ids}


@app.get("/sessions/{workflow_template_id}", dependencies=_require_agent_key)
def list_session_users(workflow_template_id: str) -> dict[str, object]:
    try:
        ids = list_session_user_ids(workflow_template_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"workflow_template_id": workflow_template_id, "user_ids": ids}


@app.get("/sessions", dependencies=_require_agent_key)
def list_session_workflow_templates() -> dict[str, object]:
    return {"workflow_template_ids": list_all_session_workflow_template_ids()}
