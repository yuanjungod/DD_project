from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.models.entities import AgentTemplate, ResourceConfig, SkillConfig, WorkflowTemplate


ROOT = Path(__file__).resolve().parents[3]
AGENT_CONFIG_DIR = ROOT / "agent_service" / "configs"
PROMPT_DIR = ROOT / "agent_service" / "prompts"


def seed_configuration_catalog(db: Session) -> None:
    if db.query(SkillConfig).count() > 0:
        return

    tools = _load_yaml(AGENT_CONFIG_DIR / "tools.yaml").get("tools", {})
    agents = _load_yaml(AGENT_CONFIG_DIR / "agents.yaml").get("agents", [])
    workflows_data = _load_yaml(AGENT_CONFIG_DIR / "workflows.yaml").get("workflows", [])

    for skill_id, config in tools.items():
        db.add(
            SkillConfig(
                id=skill_id,
                name=skill_id,
                description=config.get("description", ""),
                implementation=config.get("implementation", ""),
                input_schema={},
                output_schema={},
                requires_api_key=config.get("requires_api_key", False),
                enabled=True,
            )
        )

    resource_configs = [
        ResourceConfig(
            id="resource_public_web",
            name="公开网页与新闻源",
            type="web",
            description="用于搜索和抓取公开网页、新闻、公告和官网信息。",
            connection_config={"allowed_tools": ["search", "web_fetch"]},
        ),
        ResourceConfig(
            id="resource_uploaded_files",
            name="上传文件库",
            type="file_store",
            description="用于读取项目上传的 PDF、Word、Excel 和其他材料。",
            connection_config={"allowed_tools": ["file_reader"]},
        ),
        ResourceConfig(
            id="resource_vector_store",
            name="项目向量库",
            type="vector_store",
            description="用于检索已索引项目资料的相关片段。",
            connection_config={"allowed_tools": ["vector_retrieval"]},
        ),
    ]
    db.add_all(resource_configs)

    for agent in agents:
        skill_ids = agent.get("tools", [])
        db.add(
            AgentTemplate(
                id=agent["name"],
                name=agent["name"],
                role=agent.get("role", ""),
                prompt=_read_prompt(agent.get("prompt", "")),
                skill_ids=skill_ids,
                resource_ids=_resource_ids_for_skills(skill_ids),
                output_schema=agent.get("output_schema", "agent_result"),
                enabled=True,
            )
        )

    for workflow in workflows_data:
        ordered_agents = _ordered_agents(workflow)
        db.add(
            WorkflowTemplate(
                id=workflow["id"],
                name=workflow["name"],
                description=workflow.get("description", ""),
                scenario=workflow.get("scenario", "standard"),
                graph=_graph_from_agents(ordered_agents),
                status="published",
                version=1,
            )
        )

    db.commit()


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def _read_prompt(prompt_file: str) -> str:
    if not prompt_file:
        return ""
    path = PROMPT_DIR / prompt_file
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _resource_ids_for_skills(skill_ids: list[str]) -> list[str]:
    resource_ids: list[str] = []
    if any(skill in skill_ids for skill in ("search", "web_fetch")):
        resource_ids.append("resource_public_web")
    if "file_reader" in skill_ids:
        resource_ids.append("resource_uploaded_files")
    if "vector_retrieval" in skill_ids:
        resource_ids.append("resource_vector_store")
    return resource_ids


def _ordered_agents(workflow: dict) -> list[str]:
    return [
        workflow["coordinator"],
        *workflow.get("research_agents", []),
        *workflow.get("analysis_agents", []),
        workflow["verifier"],
        workflow["reporter"],
    ]


def _graph_from_agents(agent_ids: list[str]) -> dict:
    nodes = [
        {
            "id": f"node_{index + 1:02d}",
            "agent_template_id": agent_id,
            "stage": _stage_for_index(index, len(agent_ids)),
        }
        for index, agent_id in enumerate(agent_ids)
    ]
    edges = [
        {
            "from": nodes[index]["id"],
            "to": nodes[index + 1]["id"],
        }
        for index in range(len(nodes) - 1)
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "entry_node": nodes[0]["id"] if nodes else "",
        "report_node": nodes[-1]["id"] if nodes else "",
    }


def _stage_for_index(index: int, total: int) -> str:
    if index == 0:
        return "coordination"
    if index == total - 2:
        return "verification"
    if index == total - 1:
        return "reporting"
    return "execution"
