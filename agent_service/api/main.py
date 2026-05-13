from __future__ import annotations

from fastapi import FastAPI

from agent_service.agents.agentscope_adapter import initialize_agentscope
from agent_service.api.schemas import RunRequest, RunResult
from agent_service.workflows.config_loader import load_agent_config, load_tool_config
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
    return {
        "agents": [agent.model_dump() for agent in agent_config.agents],
        "workflow": agent_config.workflow.model_dump(),
        "tools": {name: tool.model_dump() for name, tool in tool_config.tools.items()},
    }


@app.post("/runs", response_model=RunResult)
def run_due_diligence(request: RunRequest) -> RunResult:
    return workflow.run(project_id=request.project_id, company_config=request.company_config)
