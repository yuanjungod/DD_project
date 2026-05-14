import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { deleteProject, getMe, listProjects, listWorkflowTemplates } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import { workflowName } from "../data/workflows";
import type { Project, User, WorkflowTemplate } from "../types/domain";

export function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [workflowTemplates, setWorkflowTemplates] = useState<WorkflowTemplate[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [deletingId, setDeletingId] = useState("");
  const [error, setError] = useState("");

  const canDeleteProjects = currentUser != null && currentUser.role !== "viewer";

  const refresh = useCallback(async () => {
    const [projectItems, workflowItems] = await Promise.all([listProjects(), listWorkflowTemplates()]);
    setProjects(projectItems);
    setWorkflowTemplates(workflowItems);
  }, []);

  useEffect(() => {
    getMe()
      .then(setCurrentUser)
      .catch(() => setCurrentUser(null));
  }, []);

  useEffect(() => {
    refresh().catch((err: unknown) => setError(String(err)));
  }, [refresh]);

  async function handleDelete(project: Project) {
    const ok = window.confirm(
      `确定删除应用「${project.name}」（${project.company_config.target_company.name}）吗？关联的资源、运行记录与报告将一并删除，且不可恢复。`,
    );
    if (!ok) {
      return;
    }
    setError("");
    setDeletingId(project.id);
    try {
      await deleteProject(project.id);
      await refresh();
    } catch (err: unknown) {
      setError(String(err));
    } finally {
      setDeletingId("");
    }
  }

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Applications</p>
        <h1>场景应用</h1>
        <p>这里是已经把尽调场景应用到具体公司后的项目列表。管理员与分析员可删除不再需要的应用。</p>
      </header>
      {error ? <div className="error">{error}</div> : null}
      <div className="grid two">
        {projects.map((project) => (
          <SectionCard key={project.id} title={project.name}>
            <div className="summary-box">
              <strong>{project.company_config.target_company.name}</strong>
              <span>
                {workflowName(
                  project.company_config.scope.workflow_template_id ?? project.company_config.scope.workflow_id,
                  workflowTemplates,
                )} · v
                {project.company_config.scope.workflow_template_version ?? 1}
              </span>
            </div>
            <p className="muted">{project.company_config.scope.focus_areas.join(" / ")}</p>
            <div className="row-actions">
              <Link className="button-link" to={`/projects/${project.id}`}>
                查看应用详情
              </Link>
              {canDeleteProjects ? (
                <button
                  type="button"
                  className="secondary-button"
                  disabled={deletingId === project.id}
                  onClick={() => handleDelete(project)}
                >
                  {deletingId === project.id ? "删除中…" : "删除"}
                </button>
              ) : null}
            </div>
          </SectionCard>
        ))}
      </div>
    </div>
  );
}
