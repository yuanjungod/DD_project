import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listProjects } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import { workflowName } from "../data/workflows";
import type { Project } from "../types/domain";

export function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch((err: unknown) => setError(String(err)));
  }, []);

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Applications</p>
        <h1>场景应用</h1>
        <p>这里是已经把尽调场景应用到具体公司后的项目列表。</p>
      </header>
      {error ? <div className="error">{error}</div> : null}
      <div className="grid two">
        {projects.map((project) => (
          <SectionCard key={project.id} title={project.name}>
            <div className="summary-box">
              <strong>{project.company_config.target_company.name}</strong>
              <span>
                {workflowName(project.company_config.scope.workflow_template_id ?? project.company_config.scope.workflow_id)} · v
                {project.company_config.scope.workflow_template_version ?? 1}
              </span>
            </div>
            <p className="muted">{project.company_config.scope.focus_areas.join(" / ")}</p>
            <Link className="button-link" to={`/projects/${project.id}`}>
              查看应用详情
            </Link>
          </SectionCard>
        ))}
      </div>
    </div>
  );
}
