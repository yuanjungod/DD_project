from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent_service.agents.runner import ConfiguredAgentRunner
from agent_service.execution.container_manager import get_container_manager
from agent_service.execution.context import build_run_execution_context
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
from shared.session_fields import dual_write_session_id_fields
from agent_service.workflows.agent_outputs import agent_step_output_dir, ensure_step_output_handoff
from agent_service.workflows.config_loader import AgentDefinition, WorkflowDefinition
from agent_service.workflows.graph_order import (
    resolve_graph_agent_order,
    resolve_graph_execution_levels,
    resolve_graph_node_agent_plan,
    resolve_graph_node_ids,
    resolve_graph_predecessors,
    validate_workflow_graph,
)


class WorkflowEngine:
    def step_review_chat(self, payload: StepReviewChatRequest) -> StepReviewChatResponse:
        snapshot = payload.workflow_snapshot
        if not snapshot:
            raise ValueError("workflow_snapshot is required")
        agent_definitions = self._agent_definitions_from_snapshot(snapshot)
        definition = agent_definitions.get(payload.agent_name)
        if definition is None:
            raise ValueError(f"Workflow snapshot missing agent definition: {payload.agent_name}")
        workflow_section = snapshot.get("workflow") if isinstance(snapshot.get("workflow"), dict) else {}
        execution_context = build_run_execution_context(
            workflow_runtime=workflow_section.get("runtime"),
            user_id=str(payload.user_id or "").strip(),
            workflow_template_id=str(
                payload.resolved_company_config.workflow_template_id or workflow_section.get("id") or ""
            ),
            engagement_id=str(payload.engagement_id or ""),
            session_id=str(payload.resolved_workflow_session_id or payload.engagement_id or "review"),
        )
        if execution_context.is_docker:
            get_container_manager().ensure_container(execution_context)
        runner = ConfiguredAgentRunner(definition, execution_context=execution_context)
        cur = payload.current_step
        reply = runner.run_step_review_chat(
            payload.resolved_company_config,
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
        workflow_session_id: str | None = None,
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
        graph = self._graph_from_snapshot(workflow_snapshot)
        validate_workflow_graph(graph)
        ordered_agents = self._ordered_agents(workflow)
        execution_levels = resolve_graph_execution_levels(graph)
        flat_plan = resolve_graph_node_agent_plan(graph)
        predecessor_map = resolve_graph_predecessors(graph)
        topo_node_ids = resolve_graph_node_ids(graph)
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
        resolved_session_id = (workflow_session_id or diligence_session_id or "").strip() or None
        safe_session_id = (resolved_session_id or run_id).strip()

        workflow_section = workflow_snapshot.get("workflow") if workflow_snapshot else {}
        execution_context = build_run_execution_context(
            workflow_runtime=workflow_section.get("runtime") if isinstance(workflow_section, dict) else None,
            user_id=safe_user_id,
            workflow_template_id=workflow_template_id,
            engagement_id=engagement_id,
            session_id=safe_session_id,
        )
        if execution_context.is_docker:
            get_container_manager().ensure_container(execution_context)

        recorder: object
        start_payload = {
            "run_id": run_id,
            "user_id": safe_user_id,
            "engagement_id": engagement_id,
            **dual_write_session_id_fields(resolved_session_id),
            "attempt_index": attempt_index,
            "company_config": company_config.model_dump(mode="json"),
            "workflow_meta": self._workflow_session_meta(workflow_snapshot, workflow),
            "agents_ordered": ordered_agents,
            "execution_levels": execution_levels,
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

        completed_plan_keys = {
            flat_plan[index]
            for index in range(min(resume_from_step_index, len(flat_plan)))
        }
        node_results: dict[str, list[AgentResult]] = defaultdict(list)
        for index, step in enumerate(done_steps):
            if index >= len(flat_plan):
                break
            node_id, _agent_id = flat_plan[index]
            if step.result is not None:
                node_results[node_id].append(step.result)

        step_seq = resume_from_step_index

        def predecessor_results(node_id: str) -> list[AgentResult]:
            ordered_preds = [node for node in topo_node_ids if node in predecessor_map.get(node_id, [])]
            handoff: list[AgentResult] = []
            for pred_id in ordered_preds:
                handoff.extend(node_results.get(pred_id, []))
            return handoff

        def run_node(node_id: str) -> tuple[list[AgentStep], list[AgentResult], RunResult | None]:
            node_steps: list[AgentStep] = []
            node_agent_results: list[AgentResult] = []
            node_plan = [(nid, agent_name) for nid, agent_name in flat_plan if nid == node_id]
            handoff = predecessor_results(node_id)

            for plan_node_id, agent_name in node_plan:
                if (plan_node_id, agent_name) in completed_plan_keys:
                    continue
                definition = agent_definitions.get(agent_name)
                if definition is None:
                    raise ValueError(f"Workflow snapshot missing agent definition: {agent_name}")
                runner = ConfiguredAgentRunner(definition, execution_context=execution_context)
                nonlocal step_seq
                step_seq += 1
                step = AgentStep(id=f"{run_id}_step_{step_seq:03d}", agent=agent_name, status="running")
                node_steps.append(step)
                recorder.append_event({"type": "step_started", "step_id": step.id, "agent": agent_name})
                notify_run_progress(engagement_id, run_id, step)
                inject_ctx = (
                    continuation_context
                    if step_seq == 1 and resume_from_step_index == 0
                    else None
                )
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
                        handoff + node_agent_results,
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
                    return (
                        node_steps,
                        node_agent_results,
                        RunResult(
                            run_id=run_id,
                            engagement_id=engagement_id,
                            status="failed",
                            steps=steps + node_steps,
                        ),
                    )
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
                node_agent_results.append(result)
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
            return node_steps, node_agent_results, None

        for level_idx, level_node_ids in enumerate(execution_levels):
            pending_nodes = [
                node_id
                for node_id in level_node_ids
                if any(
                    (nid, agent_name) not in completed_plan_keys
                    for nid, agent_name in flat_plan
                    if nid == node_id
                )
            ]
            if not pending_nodes:
                continue

            level_outputs: dict[str, tuple[list[AgentStep], list[AgentResult], RunResult | None]] = {}
            max_workers = max(1, len(pending_nodes))
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(run_node, node_id): node_id for node_id in pending_nodes}
                for future in futures:
                    node_id = futures[future]
                    level_outputs[node_id] = future.result()

            for node_id in level_node_ids:
                if node_id not in level_outputs:
                    continue
                node_steps, node_agent_results, failure = level_outputs[node_id]
                steps.extend(node_steps)
                results.extend(node_agent_results)
                node_results[node_id].extend(node_agent_results)
                if failure is not None:
                    recorder.finalize_failure(
                        failure.steps[-1].summary or "step failed",
                        partial_result=failure.model_dump(mode="json"),
                    )
                    return failure

            if pause_after_each_step and level_idx < len(execution_levels) - 1:
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

    def _graph_from_snapshot(self, snapshot: dict | None) -> dict[str, Any]:
        if not snapshot:
            raise ValueError("Missing workflow snapshot")
        workflow = snapshot.get("workflow")
        if not isinstance(workflow, dict):
            raise ValueError("workflow_snapshot must contain a 'workflow' object")
        graph = workflow.get("graph")
        if not isinstance(graph, dict):
            raise ValueError("workflow_snapshot.workflow must contain a 'graph' object")
        return graph

    def _workflow_from_snapshot(self, snapshot: dict | None) -> WorkflowDefinition:
        if not snapshot:
            raise ValueError("Missing workflow snapshot")
        workflow = snapshot.get("workflow")
        if not isinstance(workflow, dict):
            raise ValueError("workflow_snapshot must contain a 'workflow' object")
        graph = self._graph_from_snapshot(snapshot)
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
            runtime=workflow.get("runtime") if isinstance(workflow.get("runtime"), dict) else {},
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
