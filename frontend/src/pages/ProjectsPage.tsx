import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { cloneProjectVersion, deleteProject, getMe, listProjects, listWorkflowTemplates } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import { workflowName } from "../data/workflows";
import { projectIdentityLabel } from "../domain/projectIdentity";
import type { Project, User, WorkflowTemplate } from "../types/domain";

function projectMatchesSearch(project: Project, rawQuery: string): boolean {
  const query = rawQuery.trim().toLowerCase();
  if (!query) return true;
  const haystack = [
    project.id,
    project.application_id,
    project.name,
    project.company_config.target_company.name,
    projectIdentityLabel(project),
    String(project.version),
    `v${project.version}`,
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(query);
}

function compareProjectsByCreatedAt(a: Project, b: Project): number {
  return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
}

export function ProjectsPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [workflowTemplates, setWorkflowTemplates] = useState<WorkflowTemplate[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [deletingId, setDeletingId] = useState("");
  const [cloningId, setCloningId] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [error, setError] = useState("");

  const canManageProjects = currentUser != null && currentUser.role !== "viewer";

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

  const filteredProjects = useMemo(() => {
    return [...projects]
      .sort(compareProjectsByCreatedAt)
      .filter((project) => projectMatchesSearch(project, searchQuery));
  }, [projects, searchQuery]);

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

  async function handleClone(project: Project) {
    const ok = window.confirm(
      `复制「${projectIdentityLabel(project)}」为新版本吗？\n\n将复制公司资源、Agent 配置与上传文件，生成 v${project.version + 1}，随后可在创建应用中调整。`,
    );
    if (!ok) return;
    setError("");
    setCloningId(project.id);
    try {
      const clone = await cloneProjectVersion(project.id);
      navigate(`/projects/new?project=${encodeURIComponent(clone.id)}`);
    } catch (err: unknown) {
      setError(String(err));
    } finally {
      setCloningId("");
    }
  }

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Applications</p>
        <h1>场景应用</h1>
        <p>已落地的尽调场景应用列表。可复制任一应用为新版本并调整配置，或在场景应用中启动 Run。</p>
      </header>
      {error ? <div className="error">{error}</div> : null}
      <label className="project-app-search">
        <span className="project-app-search__label">搜索应用</span>
        <input
          type="search"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder="应用 ID、公司名称、技术 ID 等关键词"
        />
      </label>
      <div className="project-app-list">
        {filteredProjects.map((project) => (
          <SectionCard key={project.id} title={projectIdentityLabel(project)}>
            <div className="summary-box">
              <strong>{project.application_id}</strong>
              <span>
                {workflowName(
                  project.company_config.scope.workflow_template_id ?? project.company_config.scope.workflow_id,
                  workflowTemplates,
                )}{" "}
                · {project.id}
              </span>
            </div>
            <p className="muted">{project.company_config.scope.scenario}</p>
            <div className="row-actions">
              <Link className="button-link" to={`/projects/${project.id}/outputs`}>
                运行应用
              </Link>
              <Link className="button-link secondary-button" to={`/projects/new?project=${project.id}`}>
                继续配置
              </Link>
              {canManageProjects ? (
                <button
                  type="button"
                  className="secondary-button"
                  disabled={cloningId === project.id}
                  onClick={() => void handleClone(project)}
                >
                  {cloningId === project.id ? "复制中…" : "复制并配置"}
                </button>
              ) : null}
              {canManageProjects ? (
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
      {projects.length > 0 && filteredProjects.length === 0 ? (
        <p className="muted">未找到包含「{searchQuery.trim()}」的应用。</p>
      ) : null}
      {projects.length === 0 ? <p className="muted">暂无场景应用，请先在「创建应用」中新建。</p> : null}
    </div>
  );
}
