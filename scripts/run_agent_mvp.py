from __future__ import annotations

import json
from pathlib import Path
from sys import path


ROOT = Path(__file__).resolve().parents[1]
path.insert(0, str(ROOT))

from agent_service.api.schemas import CompanyConfig  # noqa: E402
from agent_service.workflows.due_diligence import DueDiligenceWorkflow  # noqa: E402


def main() -> None:
    config_path = ROOT / "shared" / "schemas" / "example_company_config.json"
    config = CompanyConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
    result = DueDiligenceWorkflow().run("proj_demo", config)
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "status": result.status,
                "steps": len(result.steps),
                "evidence": len(result.evidence),
                "report_title": result.report.title if result.report else None,
                "overall_risk": result.report.overall_risk if result.report else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
