from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from agent_service.agents.runner import ConfiguredAgentRunner
from agent_service.api.schemas import (
    AgentResult,
    AgentStep,
    CompanyConfig,
    RunResult,
    StepReviewChatRequest,
    StepReviewChatResponse,
)
from agent_service.callback_client import notify_run_progress
from agent_service.session_history import build_session_recorder, open_session_recorder_for_resume
from agent_service.workflows.agent_outputs import agent_step_output_dir, ensure_step_output_handoff
from agent_service.workflows.config_loader import AgentDefinition, WorkflowDefinition
from agent_service.workflows.graph_order import resolve_graph_agent_order


class DueDiligenceWorkflow:
    def step_review_chat(self, payload: StepReviewChatRequest) -> StepReviewChatResponse:
        snapshot = payload.workflow_snapshot
        if not snapshot:
            raise ValueError("workflow_snapshot is required")
        agent_definitions = self._agent_definitions_from_snapshot(snapshot)
        definition = agent_definitions.get(payload.agent_name)
        if definition is None:
            raise ValueError(f"Workflow snapshot missing agent definition: {payload.agent_name}")
        runner = ConfiguredAgentRunner(definition)
        cur = payload.current_step
        reply = runner.run_step_review_chat(
            payload.company_config,
            payload.previous_results,
            current_step_summary=cur.summary or "",
            current_output_dir=cur.result.output_dir if cur.result else "",
            chat_messages=payload.chat_messages,
            user_message=payload.user_message,
        )
        return StepReviewChatResponse(reply=reply)

    def run(
        self,
        engagement_id: str,
        company_config: CompanyConfig,
        workflow_snapshot: dict | None = None,
        run_id_override: str | None = None,
        *,
        user_id: str,
        diligence_session_id: str | None = None,
        attempt_index: int | None = None,
        continuation_context: dict[str, Any] | None = None,
        pause_after_each_step: bool = False,
        resume_from_step_index: int = 0,
        completed_steps: list[AgentStep] | None = None,
    ) -> RunResult:
        run_id = run_id_override or f"run_{uuid4().hex[:12]}"
        done_steps = list(completed_steps or [])
        if resume_from_step_index != len(done_steps):
            raise ValueError(
                f"resume_from_step_index ({resume_from_step_index}) must equal len(completed_steps) ({len(done_steps)})"
            )

        if not workflow_snapshot:
            raise ValueError("workflow_snapshot is required")
        workflow = self._workflow_from_snapshot(workflow_snapshot)
        workflow_template_id = company_config.workflow_template_id
        agent_definitions = self._agent_definitions_from_snapshot(workflow_snapshot)
        steps: list[AgentStep] = list(done_steps)
        results: list[AgentResult] = []
        for st in steps:
            if st.result is not None:
                results.append(st.result)
        ordered_agents = self._ordered_agents(workflow)
        if workflow_snapshot:
            missing = [a for a in ordered_agents if a not in agent_definitions]
            if missing:
                defined = sorted(agent_definitions.keys())
                raise ValueError(
                    "Workflow graph references agent_template_id that are missing from "
                    "workflow_snapshot.agent_templates (compare each node's agent_template_id "
                    f"to agent_templates[].id). missing={missing!r}; defined_ids={defined!r}"
                )

        if not user_id.strip():
            raise ValueError("user_id is required")
        safe_user_id = user_id.strip()
        safe_session_id = (diligence_session_id or run_id).strip()

        recorder: object
        start_payload = {
            "run_id": run_id,
            "user_id": safe_user_id,
            "engagement_id": engagement_id,
            "diligence_session_id": diligence_session_id,
            "attempt_index": attempt_index,
            "company_config": company_config.model_dump(mode="json"),
            "workflow_meta": self._workflow_session_meta(workflow_snapshot, workflow),
            "agents_ordered": ordered_agents,
            "pause_after_each_step": pause_after_each_step,
        }
        resumed = open_session_recorder_for_resume(
            workflow_template_id,
            safe_user_id,
            engagement_id,
            run_id,
            session_id=safe_session_id,
        )
        if resume_from_step_index > 0 and resumed is not None:
            recorder = resumed
            recorder.append_event(
                {
                    "type": "run_resumed",
                    "resume_from_step_index": resume_from_step_index,
                },
            )
        else:
            recorder = build_session_recorder(
                workflow_template_id,
                safe_user_id,
                engagement_id,
                run_id,
                session_id=safe_session_id,
            )
            recorder.start(start_payload)

        for step_idx in range(resume_from_step_index, len(ordered_agents)):
            agent_name = ordered_agents[step_idx]
            definition = agent_definitions.get(agent_name)
            if definition is None:
                raise ValueError(f"Workflow snapshot missing agent definition: {agent_name}")
            runner = ConfiguredAgentRunner(definition)
            step = AgentStep(id=f"{run_id}_step_{step_idx + 1:03d}", agent=agent_name, status="running")
            steps.append(step)
            recorder.append_event({"type": "step_started", "step_id": step.id, "agent": agent_name})
            notify_run_progress(engagement_id, run_id, step)
            inject_ctx = continuation_context if step_idx == 0 and resume_from_step_index == 0 else None
            planned_output_dir = str(
                agent_step_output_dir(
                    workflow_template_id=workflow_template_id,
                    user_id=safe_user_id,
                    engagement_id=engagement_id,
                    session_id=safe_session_id,
                    run_id=run_id,
                    step_id=step.id,
                    agent_name=agent_name,
                )
            )
            Path(planned_output_dir).mkdir(parents=True, exist_ok=True)
            try:
                result = runner.run(
                    company_config,
                    results,
                    continuation_context=inject_ctx,
                    agent_output_dir=planned_output_dir,
                )
            except Exception as exc:
                msg = str(exc)
                step.status = "failed"
                step.summary = msg
                step.result = None
                recorder.append_event(
                    {
                        "type": "step_failed",
                        "step_id": step.id,
                        "agent": agent_name,
                        "error": msg,
                    },
                )
                rr = RunResult(
                    run_id=run_id,
                    engagement_id=engagement_id,
                    status="failed",
                    steps=steps,
                )
                recorder.finalize_failure(msg, partial_result=rr.model_dump(mode="json"))
                return rr
            step.status = result.status
            finalized_dir, output_readme_path = ensure_step_output_handoff(
                planned_output_dir,
                agent=agent_name,
                step_id=step.id,
                status=result.status,
                summary=step.summary or "",
            )
            result.output_dir = finalized_dir
            result.output_readme_path = output_readme_path
            step.result = result
            results.append(result)
            notify_run_progress(engagement_id, run_id, step)
            recorder.append_event(
                {
                    "type": "step_completed",
                    "step_id": step.id,
                    "agent": agent_name,
                    "output_dir": finalized_dir,
                    "output_readme_path": output_readme_path,
                },
            )
            if pause_after_each_step and step_idx < len(ordered_agents) - 1:
                rr = RunResult(
                    run_id=run_id,
                    engagement_id=engagement_id,
                    status="paused",
                    steps=steps,
                )
                recorder.mark_paused(rr.model_dump(mode="json"))
                return rr

        rr = RunResult(
            run_id=run_id,
            engagement_id=engagement_id,
            status="completed",
            steps=steps,
        )
        recorder.finalize_success(rr.model_dump(mode="json"))
        return rr

    def _workflow_session_meta(self, workflow_snapshot: dict | None, workflow: WorkflowDefinition) -> dict[str, object]:
        if workflow_snapshot and "workflow" in workflow_snapshot:
            w = workflow_snapshot["workflow"]
            graph = w.get("graph") or {}
            ids = resolve_graph_agent_order(graph)
            return {
                "source": "workflow_snapshot",
                "workflow_template_id": w.get("id"),
                "workflow_name": w.get("name"),
                "workflow_version": w.get("version"),
                "workflow_template": w.get("workflow_template"),
                "graph_agent_order": ids,
            }
        return {
            "source": "static_workflow_config",
            "workflow_template_id": workflow.id,
            "workflow_name": workflow.name,
            "workflow_version": None,
            "workflow_template": getattr(workflow, "workflow_template", "standard"),
            "graph_agent_order": self._ordered_agents(workflow),
        }

    def _ordered_agents(self, workflow: WorkflowDefinition) -> list[str]:
        configured = workflow.ordered_agents or [
            workflow.coordinator,
            *workflow.research_agents,
            *workflow.analysis_agents,
            workflow.reporter,
        ]
        ordered: list[str] = []
        seen: set[str] = set()
        for agent_name in configured:
            if agent_name and agent_name not in seen:
                ordered.append(agent_name)
                seen.add(agent_name)
        return ordered

    def _workflow_from_snapshot(self, snapshot: dict | None) -> WorkflowDefinition:
        if not snapshot:
            raise ValueError("Missing workflow snapshot")
        workflow = snapshot.get("workflow")
        if not isinstance(workflow, dict):
            raise ValueError("workflow_snapshot must contain a 'workflow' object")
        graph = workflow.get("graph")
        if not isinstance(graph, dict):
            raise ValueError("workflow_snapshot.workflow must contain a 'graph' object")
        agent_ids = resolve_graph_agent_order(graph)
        if not agent_ids:
            raise ValueError(
                "Workflow snapshot graph must include at least one node with agent_template_id. "
                "Check entry_node, edges, and that at least one execution node sets agent_template_id."
            )
        return WorkflowDefinition(
            id=workflow["id"],
            name=workflow["name"],
            description=workflow.get("description", ""),
            workflow_template=workflow.get("workflow_template", "standard"),
            ordered_agents=agent_ids,
            coordinator=agent_ids[0],
            research_agents=agent_ids[1:-1] if len(agent_ids) >= 2 else agent_ids[1:],
            analysis_agents=[],
            verifier="",
            reporter=agent_ids[-1] if len(agent_ids) >= 2 else "",
        )

    def _agent_definitions_from_snapshot(self, snapshot: dict | None) -> dict[str, AgentDefinition]:
        if not snapshot:
            return {}
        definitions: dict[str, AgentDefinition] = {}
        skill_packages = {
            skill_package["id"]: skill_package
            for skill_package in snapshot.get("skill_packages", [])
        }
        tool_configs = {
            tool["id"]: tool
            for tool in snapshot.get("tools", [])
        }
        resource_configs = {
            resource["id"]: resource
            for resource in snapshot.get("resources", [])
        }
        for agent in snapshot.get("agent_templates", []):
            agent_skill_packages = [
                skill_packages[skill_id]
                for skill_id in agent.get("skill_package_ids", [])
                if skill_id in skill_packages
            ]
            agent_tool_configs = [
                tool_configs[tool_id]
                for tool_id in agent.get("tool_ids", [])
                if tool_id in tool_configs
            ]
            agent_resource_configs = [
                resource_configs[resource_id]
                for resource_id in agent.get("resource_ids", [])
                if resource_id in resource_configs
            ]
            package_instructions = "\n\n".join(
                skill_package["skill_md"]
                for skill_package in agent_skill_packages
            )
            prompt_text = "\n\n".join(part for part in [package_instructions, agent.get("prompt", "")] if part)
            definitions[agent["id"]] = AgentDefinition(
                name=agent["id"],
                role=agent.get("role", ""),
                prompt="",
                sub_agent_ids=agent.get("sub_agent_ids", []),
                prompt_text=prompt_text,
                skill_package_ids=agent.get("skill_package_ids", []),
                tool_ids=agent.get("tool_ids", []),
                resource_ids=agent.get("resource_ids", []),
                platform_upload_file_ids=list(agent.get("platform_upload_file_ids") or []),
                skill_packages=agent_skill_packages,
                tool_configs=agent_tool_configs,
                resource_configs=agent_resource_configs,
                react_config=agent.get("react_config", {}),
            )
        return definitions
