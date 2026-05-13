import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listScenarios } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import type { Scenario } from "../types/domain";

export function ScenariosPage() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    listScenarios()
      .then(setScenarios)
      .catch((err: unknown) => setError(String(err)));
  }, []);

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Step 1</p>
        <h1>创建尽调场景</h1>
        <p>场景是可复用的 Agent 流程模板。先配置好流程，再把它应用到不同公司。</p>
      </header>
      {error ? <div className="error">{error}</div> : null}
      <div className="scenario-grid">
        {scenarios.map((scenario) => (
          <SectionCard key={scenario.id} title={scenario.name} description={scenario.description}>
            <div className="tag-row">
              <span>{scenario.scenario}</span>
              <span>{scenario.agents.length} agents</span>
            </div>
            <ol className="agent-chain">
              {scenario.agents.map((agent) => (
                <li key={agent}>{agent}</li>
              ))}
            </ol>
            <Link className="button-link" to={`/projects/new?workflow=${scenario.id}`}>
              应用到公司
            </Link>
          </SectionCard>
        ))}
      </div>
    </div>
  );
}
