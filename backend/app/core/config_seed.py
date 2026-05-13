from __future__ import annotations

from pathlib import Path

import json

import yaml
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.entities import AgentTemplate, ResourceConfig, SkillPackage, ToolConfig, WorkflowTemplate


ROOT = Path(__file__).resolve().parents[3]
AGENT_CONFIG_DIR = ROOT / "agent_service" / "configs"
PROMPT_DIR = ROOT / "agent_service" / "prompts"


def seed_configuration_catalog(db: Session) -> None:
    ensure_configuration_schema(db)

    tools = _load_yaml(AGENT_CONFIG_DIR / "tools.yaml").get("tools", {})
    agents = _load_yaml(AGENT_CONFIG_DIR / "agents.yaml").get("agents", [])
    workflows_data = _load_yaml(AGENT_CONFIG_DIR / "workflows.yaml").get("workflows", [])

    if db.query(ToolConfig).count() == 0:
        for tool_id, config in tools.items():
            db.add(
                ToolConfig(
                    id=tool_id,
                    name=tool_id,
                    description=config.get("description", ""),
                    implementation=config.get("implementation", ""),
                    input_schema={},
                    output_schema={},
                    requires_api_key=config.get("requires_api_key", False),
                    enabled=True,
                )
            )

    if db.query(SkillPackage).count() == 0:
        db.add_all(_default_skill_packages())

    if db.query(ResourceConfig).count() == 0:
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
            )
        ]
        db.add_all(resource_configs)

    if db.query(AgentTemplate).count() == 0:
        for agent in agents:
            tool_ids = agent.get("tools", [])
            db.add(
                AgentTemplate(
                    id=agent["name"],
                    name=agent["name"],
                    role=agent.get("role", ""),
                    prompt=_read_prompt(agent.get("prompt", "")),
                    skill_package_ids=_skill_package_ids_for_agent(agent["name"]),
                    tool_ids=tool_ids,
                    skill_ids=tool_ids,
                    resource_ids=_resource_ids_for_tools(tool_ids),
                    react_config=_default_react_config(),
                    output_schema=agent.get("output_schema", "agent_result"),
                    enabled=True,
                )
            )
    else:
        for agent_template in db.query(AgentTemplate).all():
            tool_ids = agent_template.tool_ids or agent_template.skill_ids or []
            changed = False
            if not agent_template.tool_ids:
                agent_template.tool_ids = tool_ids
                changed = True
            if not agent_template.skill_package_ids:
                agent_template.skill_package_ids = _skill_package_ids_for_agent(agent_template.id)
                changed = True
            react_config = agent_template.react_config or {}
            if not react_config or "model" not in react_config:
                agent_template.react_config = _merge_react_config(react_config)
                changed = True
            if changed:
                db.add(agent_template)

    if db.query(WorkflowTemplate).count() == 0:
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


def ensure_configuration_schema(db: Session) -> None:
    columns = _table_columns(db, "agent_templates")
    if columns and "skill_package_ids" not in columns:
        db.execute(text("ALTER TABLE agent_templates ADD COLUMN skill_package_ids JSON DEFAULT '[]'"))
    if columns and "tool_ids" not in columns:
        db.execute(text("ALTER TABLE agent_templates ADD COLUMN tool_ids JSON DEFAULT '[]'"))
    if columns and "react_config" not in columns:
        default_value = json.dumps(_default_react_config())
        db.execute(text(f"ALTER TABLE agent_templates ADD COLUMN react_config JSON DEFAULT '{default_value}'"))
    db.commit()


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def _read_prompt(prompt_file: str) -> str:
    if not prompt_file:
        return ""
    path = PROMPT_DIR / prompt_file
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _default_react_config() -> dict:
    return {
        "max_iters": 6,
        "parallel_tool_calls": False,
        "model": {
            "baseUrl": "http://127.0.0.1:8081/v1",
            "apiKey": "yuanjun",
            "api": "anthropic-messages",
            "models": [
                {
                    "id": "kimi-code",
                    "name": "kimi-code(Custom Provider)",
                    "reasoning": True,
                    "input": ["text", "image"],
                    "cost": {
                        "input": 0,
                        "output": 0,
                        "cacheRead": 0,
                        "cacheWrite": 0,
                    },
                    "contextWindow": 128000,
                    "maxTokens": 4096,
                }
            ],
        },
    }


def _merge_react_config(existing: dict) -> dict:
    merged = _default_react_config()
    merged.update(existing)
    merged["model"] = existing.get("model") or merged["model"]
    return merged


def _table_columns(db: Session, table_name: str) -> set[str]:
    rows = db.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def _default_skill_packages() -> list[SkillPackage]:
    packages = [
        (
            "skill_due_diligence_core",
            "due-diligence-core",
            "Guides evidence-first due diligence work with source-backed claims, confidence, conflicts, and report-ready findings.",
            "# Due Diligence Core\n\nAlways ground material claims in evidence IDs. Mark uncertainty explicitly. Preserve conflicts instead of hiding them.",
        ),
        (
            "skill_legal_risk_review",
            "legal-risk-review",
            "Guides review of litigation, sanctions, penalties, intellectual property, compliance, and regulatory risks.",
            "# Legal Risk Review\n\nCheck litigation, administrative penalties, sanctions, IP disputes, data compliance, employment disputes, and regulatory exposure.",
        ),
        (
            "skill_financial_signal_analysis",
            "financial-signal-analysis",
            "Guides financial diligence over funding, revenue signals, cash flow hints, disclosure gaps, and business model quality.",
            "# Financial Signal Analysis\n\nSeparate facts from estimates. Do not infer precise numbers unless evidence provides them. Highlight missing disclosure.",
        ),
        (
            "skill_market_competition_analysis",
            "market-competition-analysis",
            "Guides market, competitor, product positioning, defensibility, and industry risk analysis.",
            "# Market Competition Analysis\n\nUse configured competitors and public sources. Separate company-specific risks from industry-level risks.",
        ),
        (
            "skill_report_writing",
            "due-diligence-report-writing",
            "Guides concise due diligence report writing with executive summaries, risk levels, evidence IDs, and open diligence gaps.",
            "# Due Diligence Report Writing\n\nEvery section must include evidence IDs. Do not hide uncertainty. Use the requested report language.",
        ),
    ]
    return [
        SkillPackage(
            id=package_id,
            name=directory_name,
            description=description,
            directory_name=directory_name,
            skill_md=_skill_md(directory_name, description, body),
            resources_manifest={"files": ["SKILL.md"], "references": [], "scripts": [], "assets": []},
            enabled=True,
        )
        for package_id, directory_name, description, body in packages
    ]


def _skill_md(name: str, description: str, body: str) -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n"


def _skill_package_ids_for_agent(agent_name: str) -> list[str]:
    mapping = {
        "CoordinatorAgent": ["skill_due_diligence_core"],
        "CompanyProfileAgent": ["skill_due_diligence_core"],
        "WebResearchAgent": ["skill_due_diligence_core"],
        "FinancialAnalysisAgent": ["skill_due_diligence_core", "skill_financial_signal_analysis"],
        "LegalRiskAgent": ["skill_due_diligence_core", "skill_legal_risk_review"],
        "IndustryAnalysisAgent": ["skill_due_diligence_core", "skill_market_competition_analysis"],
        "EvidenceVerifierAgent": ["skill_due_diligence_core"],
        "ReportWriterAgent": ["skill_due_diligence_core", "skill_report_writing"],
    }
    return mapping.get(agent_name, ["skill_due_diligence_core"])


def _resource_ids_for_tools(tool_ids: list[str]) -> list[str]:
    resource_ids: list[str] = []
    if any(tool in tool_ids for tool in ("search", "web_fetch")):
        resource_ids.append("resource_public_web")
    if "file_reader" in tool_ids:
        resource_ids.append("resource_uploaded_files")
    if "vector_retrieval" in tool_ids:
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
