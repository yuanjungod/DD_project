from __future__ import annotations

from typing import Any

from agent_service.api.schemas import CompanyConfig
from agent_service.tools.base import ToolExecutionContext


class MockSearchTool:
    """Deterministic search stand-in for local MVP runs."""

    def run(self, query: str, company_config: CompanyConfig, agent_name: str) -> dict[str, Any]:
        company = company_config.target_company
        return {
            "title": f"Search result for {query}",
            "source_type": "mock",
            "source_url": None,
            "excerpt": (
                f"Mock source for {company.name}: query '{query}' within "
                f"{company_config.scope.time_range}."
            ),
            "confidence": 0.68,
            "collected_by": agent_name,
            "metadata": {"query": query},
        }

    def execute(self, payload: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
        company_config = context.company_config
        query = payload.get("query") or f"{company_config.target_company.name} {context.agent_role}"
        return {"source": self.run(str(query), company_config, context.agent_name)}


class MockWebFetchTool:
    def run(self, url: str, company_config: CompanyConfig, agent_name: str) -> dict[str, Any]:
        company = company_config.target_company
        return {
            "title": f"Fetched page for {company.name}",
            "source_type": "mock",
            "source_url": url or None,
            "excerpt": f"Mock page content describes {company.name} and its public positioning.",
            "confidence": 0.7,
            "collected_by": agent_name,
            "metadata": {"url": url},
        }

    def execute(self, payload: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
        company_config = context.company_config
        url = payload.get("url") or ""
        return {"source": self.run(str(url), company_config, context.agent_name)}


class MockFileReaderTool:
    def run(self, file_id: str, company_config: CompanyConfig, agent_name: str) -> dict[str, Any]:
        return {
            "title": f"Uploaded file {file_id}",
            "source_type": "file",
            "file_id": file_id,
            "excerpt": f"Mock extracted content from uploaded file {file_id}.",
            "confidence": 0.72,
            "collected_by": agent_name,
            "metadata": {"file_id": file_id},
        }

    def execute(self, payload: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
        visible = context.visible_uploaded_file_ids()
        file_id = payload.get("file_id") or next(iter(visible), "")
        return {"source": self.run(str(file_id), context.company_config, context.agent_name)}


class MockVectorRetrievalTool:
    def run(self, query: str, company_config: CompanyConfig, agent_name: str) -> dict[str, Any]:
        return {
            "title": f"Retrieved resource chunk for {query}",
            "source_type": "mock",
            "excerpt": f"Mock vector retrieval found context for '{query}'.",
            "confidence": 0.62,
            "collected_by": agent_name,
            "metadata": {"query": query},
        }

    def execute(self, payload: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
        company_config = context.company_config
        query = payload.get("query") or company_config.target_company.name
        return {"source": self.run(str(query), company_config, context.agent_name)}
