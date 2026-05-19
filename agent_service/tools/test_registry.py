from __future__ import annotations

import unittest

from agent_service.tools.registry import ToolRegistry, verify_catalog_implementations
from agent_service.workflows.config_loader import load_tool_config


class ToolRegistryTests(unittest.TestCase):
    def test_tools_yaml_implementations_resolve(self) -> None:
        catalog = load_tool_config()
        configs = [
            {"id": tool_id, "implementation": entry.implementation, "enabled": True}
            for tool_id, entry in catalog.tools.items()
        ]
        errors = verify_catalog_implementations(configs)
        self.assertEqual(errors, [], "\n".join(errors))

    def test_registry_includes_handoff_when_missing_from_snapshot(self) -> None:
        registry = ToolRegistry([{"id": "search", "implementation": "agent_service.tools.research.MockSearchTool"}])
        self.assertIn("agent_output_reader", registry._configs)
        self.assertIn("search", registry._configs)


if __name__ == "__main__":
    unittest.main()
