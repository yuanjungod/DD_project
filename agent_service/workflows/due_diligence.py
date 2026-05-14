from __future__ import annotations

from typing import Any
from uuid import uuid4

from agent_service.agents.runner import ConfiguredAgentRunner
from agent_service.api.schemas import (
    AgentResult,
    AgentStep,
    CompanyConfig,
    Evidence,
    RunResult,
    StepReviewChatRequest,
    StepReviewChatResponse,
)
from agent_service.callback_client import notify_run_progress
from agent_service.session_history import build_session_recorder, open_session_recorder_for_resume
from agent_service.tools.stores import EvidenceStoreTool
from agent_service.workflows.agent_outputs import write_agent_step_output_folder
from agent_service.workflows.config_loader import (
    AgentConfig,
    AgentDefinition,
    WorkflowConfig,
    WorkflowDefinition,
    load_agent_config,
    load_workflow_config,
)


class DueDiligenceWorkflow:
    def __init__(self) -> None:
        self._agent_config: AgentConfig | None = None
        self._workflow_config: WorkflowConfig | None = None

    def step_review_chat(self, payload: StepReviewChatRequest) -> StepReviewChatResponse:
        snapshot = payload.workflow_snapshot
        agent_definitions = self._agent_definitions_from_snapshot(snapshot)
        definition = agent_definitions.get(payload.agent_name) if agent_definitions else None
        if definition is None:
            if snapshot:
                raise ValueError(f"Workflow snapshot missing agent definition: {payload.agent_name}")
            definition = self._legacy_agent_config().get_agent(payload.agent_name)
        evidence_store = EvidenceStoreTool(id_prefix="review")
        runner = ConfiguredAgentRunner(definition, evidence_store)
        cur = payload.current_step
        findings: list[dict[str, Any]] = []
        if cur.result and cur.result.findings:
            findings = [f.model_dump(mode="json") for f in cur.result.findings]
        summary = cur.summary or (cur.result.summary if cur.result else "")
        reply = runner.run_step_review_chat(
            payload.company_config,
            payload.previous_results,
            current_step_summary=summary,
            current_findings=findings,
            chat_messages=payload.chat_messages,
            user_message=payload.user_message,
        )
        return StepReviewChatResponse(reply=reply)

    def run(
        self,
        project_id: str,
        company_config: CompanyConfig,
        workflow_snapshot: dict | None = None,
        run_id_override: str | None = None,
        *,
        diligence_session_id: str | None = None,
        attempt_index: int | None = None,
        continuation_context: dict[str, Any] | None = None,
        pause_after_each_step: bool = False,
        resume_from_step_index: int = 0,
        completed_steps: list[AgentStep] | None = None,
        completed_evidence: list[Evidence] | None = None,
    ) -> RunResult:
        run_id = run_id_override or f"run_{uuid4().hex[:12]}"
        done_steps = list(completed_steps or [])
        done_evidence = list(completed_evidence or [])
        if resume_from_step_index != len(done_steps):
            raise ValueError(
                f"resume_from_step_index ({resume_from_step_index}) must equal len(completed_steps) ({len(done_steps)})"
            )

        workflow = (
            self._workflow_from_snapshot(workflow_snapshot)
            if workflow_snapshot
            else self._legacy_workflow_config().get_workflow(company_config.scope.workflow_id)
        )
        agent_definitions = self._agent_definitions_from_snapshot(workflow_snapshot)
        evidence_store = EvidenceStoreTool(id_prefix=run_id)
        evidence_store.seed(done_evidence)
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

        recorder: object
        start_payload = {
            "run_id": run_id,
            "project_id": project_id,
            "diligence_session_id": diligence_session_id,
            "attempt_index": attempt_index,
            "company_config": company_config.model_dump(mode="json"),
            "workflow_meta": self._workflow_session_meta(workflow_snapshot, workflow),
            "agents_ordered": ordered_agents,
            "pause_after_each_step": pause_after_each_step,
        }
        resumed = open_session_recorder_for_resume(project_id, run_id)
        if resume_from_step_index > 0 and resumed is not None:
            recorder = resumed
            recorder.append_event(
                {
                    "type": "run_resumed",
                    "resume_from_step_index": resume_from_step_index,
                },
            )
        else:
            recorder = build_session_recorder(project_id, run_id)
            recorder.start(start_payload)

        for step_idx in range(resume_from_step_index, len(ordered_agents)):
            agent_name = ordered_agents[step_idx]
            definition = (
                agent_definitions.get(agent_name) if agent_definitions else self._legacy_agent_config().get_agent(agent_name)
            )
            if definition is None:
                raise ValueError(f"Workflow snapshot missing agent definition: {agent_name}")
            runner = ConfiguredAgentRunner(definition, evidence_store)
            step = AgentStep(id=f"{run_id}_step_{step_idx + 1:03d}", agent=agent_name, status="running")
            steps.append(step)
            recorder.append_event({"type": "step_started", "step_id": step.id, "agent": agent_name})
            notify_run_progress(project_id, run_id, step, evidence_delta=[])
            inject_ctx = continuation_context if step_idx == 0 and resume_from_step_index == 0 else None
            try:
                result = runner.run(company_config, results, continuation_context=inject_ctx)
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
                    project_id=project_id,
                    status="failed",
                    steps=steps,
                )
                recorder.finalize_failure(msg, partial_result=rr.model_dump(mode="json"))
                return rr
            step.status = result.status
            step.summary = result.summary
            output_dir, output_readme_path = write_agent_step_output_folder(
                project_id=project_id,
                run_id=run_id,
                step_id=step.id,
                result=result,
            )
            step.result = result
            results.append(result)
            notify_run_progress(project_id, run_id, step, evidence_delta=list(result.evidence))
            recorder.append_event(
                {
                    "type": "step_completed",
                    "step_id": step.id,
                    "agent": agent_name,
                    "evidence_count": len(result.evidence),
                    "findings_count": len(result.findings),
                    "output_dir": output_dir,
                    "output_readme_path": output_readme_path,
                },
            )
            if pause_after_each_step and step_idx < len(ordered_agents) - 1:
                rr = RunResult(
                    run_id=run_id,
                    project_id=project_id,
                    status="paused",
                    steps=steps,
                )
                recorder.mark_paused(rr.model_dump(mode="json"))
                return rr

        rr = RunResult(
            run_id=run_id,
            project_id=project_id,
            status="completed",
            steps=steps,
        )
        recorder.finalize_success(rr.model_dump(mode="json"))
        return rr

    def _workflow_session_meta(self, workflow_snapshot: dict | None, workflow: WorkflowDefinition) -> dict[str, object]:
        if workflow_snapshot and "workflow" in workflow_snapshot:
            w = workflow_snapshot["workflow"]
            graph = w.get("graph") or {}
            ids = self._agent_ids_from_graph(graph)
            return {
                "source": "workflow_snapshot",
                "workflow_id": w.get("id"),
                "workflow_name": w.get("name"),
                "workflow_version": w.get("version"),
                "scenario": w.get("scenario"),
                "graph_agent_order": ids,
            }
        return {
            "source": "static_workflow_config",
            "workflow_id": workflow.id,
            "workflow_name": workflow.name,
            "workflow_version": None,
            "scenario": getattr(workflow, "scenario", "standard"),
            "graph_agent_order": self._ordered_agents(workflow),
        }

    def _ordered_agents(self, workflow: WorkflowDefinition) -> list[str]:
        configured = workflow.ordered_agents or [
            workflow.coordinator,
            *workflow.research_agents,
            *workflow.analysis_agents,
            workflow.verifier,
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
        agent_ids = self._agent_ids_from_graph(graph)
        if not agent_ids:
            raise ValueError(
                "Workflow snapshot graph must include at least one node with agent_template_id. "
                "Check entry_node, edges, and that at least one execution node sets agent_template_id."
            )
        return WorkflowDefinition(
            id=workflow["id"],
            name=workflow["name"],
            description=workflow.get("description", ""),
            scenario=workflow.get("scenario", "standard"),
            ordered_agents=agent_ids,
            coordinator=agent_ids[0],
            research_agents=agent_ids[1:-2] if len(agent_ids) >= 3 else agent_ids[1:],
            analysis_agents=[],
            verifier=agent_ids[-2] if len(agent_ids) >= 3 else "",
            reporter=agent_ids[-1] if len(agent_ids) >= 3 else "",
        )

    def _agent_ids_from_graph(self, graph: dict[str, Any]) -> list[str]:
        nodes = [node for node in graph.get("nodes", []) if isinstance(node, dict)]
        if not nodes:
            return []
        by_node_id = {str(node.get("id")): node for node in nodes if node.get("id")}
        ordered_node_ids: list[str] = []
        current = str(graph.get("entry_node") or nodes[0].get("id") or "")
        outgoing: dict[str, str] = {}
        for edge in graph.get("edges", []):
            if isinstance(edge, dict) and edge.get("from") and edge.get("to"):
                outgoing[str(edge["from"])] = str(edge["to"])
        seen: set[str] = set()
        while current and current in by_node_id and current not in seen:
            ordered_node_ids.append(current)
            seen.add(current)
            current = outgoing.get(current, "")
        for node in nodes:
            node_id = str(node.get("id") or "")
            if node_id and node_id not in seen:
                ordered_node_ids.append(node_id)
        return [
            str(by_node_id[node_id].get("agent_template_id"))
            for node_id in ordered_node_ids
            if by_node_id[node_id].get("agent_template_id")
        ]

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
                for tool_id in agent.get("tool_ids", []) or agent.get("skill_ids", [])
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
                prompt_text=prompt_text,
                tools=agent.get("tool_ids") or agent.get("skill_ids", []),
                skill_package_ids=agent.get("skill_package_ids", []),
                tool_ids=agent.get("tool_ids") or agent.get("skill_ids", []),
                resource_ids=agent.get("resource_ids", []),
                platform_upload_file_ids=list(agent.get("platform_upload_file_ids") or []),
                skill_packages=agent_skill_packages,
                tool_configs=agent_tool_configs,
                resource_configs=agent_resource_configs,
                react_config=agent.get("react_config", {}),
            )
        return definitions

    def _legacy_agent_config(self) -> AgentConfig:
        if self._agent_config is None:
            self._agent_config = load_agent_config()
        return self._agent_config

    def _legacy_workflow_config(self) -> WorkflowConfig:
        if self._workflow_config is None:
            self._workflow_config = load_workflow_config()
        return self._workflow_config
