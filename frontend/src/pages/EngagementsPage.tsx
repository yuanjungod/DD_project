import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { cloneEngagementVersion, deleteEngagement, getMe, listEngagements, listWorkflowTemplates } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import { workflowName } from "../data/workflows";
import { workflowTemplateIdFromInstance } from "../domain/instanceConfig";
import { engagementConfig, engagementIdentityLabel } from "../domain/engagementIdentity";
import { ENGAGEMENT_LABELS } from "../domain/engagementLabels";
import { subjectNameFromConfig, taskNameFromConfig } from "../domain/instanceConfig";
import type { Engagement, User, WorkflowTemplate } from "../types/domain";

function engagementMatchesSearch(engagement: Engagement, rawQuery: string): boolean {
  const query = rawQuery.trim().toLowerCase();
  if (!query) return true;
  const haystack = [
    engagement.id,
    engagement.name,
    taskNameFromConfig(engagementConfig(engagement)),
    subjectNameFromConfig(engagementConfig(engagement)),
    engagementIdentityLabel(engagement),
    String(engagement.version),
    `v${engagement.version}`,
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(query);
}

function compareEngagementsByCreatedAt(a: Engagement, b: Engagement): number {
  return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
}

export function EngagementsPage() {
  const navigate = useNavigate();
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [workflowTemplates, setWorkflowTemplates] = useState<WorkflowTemplate[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [deletingId, setDeletingId] = useState("");
  const [cloningId, setCloningId] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [error, setError] = useState("");

  const canManageEngagements = currentUser != null && currentUser.role !== "viewer";

  const refresh = useCallback(async () => {
    const [engagementItems, workflowItems] = await Promise.all([listEngagements(), listWorkflowTemplates()]);
    setEngagements(engagementItems);
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

  const filteredEngagements = useMemo(() => {
    return [...engagements]
      .sort(compareEngagementsByCreatedAt)
      .filter((engagement) => engagementMatchesSearch(engagement, searchQuery));
  }, [engagements, searchQuery]);

  async function handleDelete(engagement: Engagement) {
    const ok = window.confirm(
      `确定删除任务「${taskNameFromConfig(engagementConfig(engagement)) || engagement.name}」吗？关联的资源、运行记录与报告将一并删除，且不可恢复。`,
    );
    if (!ok) {
      return;
    }
    setError("");
    setDeletingId(engagement.id);
    try {
      await deleteEngagement(engagement.id);
      await refresh();
    } catch (err: unknown) {
      setError(String(err));
    } finally {
      setDeletingId("");
    }
  }

  async function handleClone(engagement: Engagement) {
    const ok = window.confirm(
      `复制「${engagementIdentityLabel(engagement)}」为新版本吗？\n\n将复制实例资源、Agent 配置与上传文件，生成 v${engagement.version + 1}，随后可在「${ENGAGEMENT_LABELS.createNav}」中调整。`,
    );
    if (!ok) return;
    setError("");
    setCloningId(engagement.id);
    try {
      const clone = await cloneEngagementVersion(engagement.id);
      navigate(`/engagements/new?engagement=${encodeURIComponent(clone.id)}`);
    } catch (err: unknown) {
      setError(String(err));
    } finally {
      setCloningId("");
    }
  }

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">任务</p>
        <h1>{ENGAGEMENT_LABELS.listTitle}</h1>
        <p>已创建的任务。可复制为新版本并调整配置，或直接启动运行。</p>
      </header>
      {error ? <div className="error">{error}</div> : null}
      <label className="engagement-app-search">
        <span className="engagement-app-search__label">搜索任务</span>
        <input
          type="search"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder="任务名称、模板、版本等关键词"
        />
      </label>
      <div className="engagement-app-list">
        {filteredEngagements.map((engagement) => (
          <SectionCard key={engagement.id} title={engagementIdentityLabel(engagement)}>
            <div className="summary-box">
              <strong>{taskNameFromConfig(engagementConfig(engagement)) || engagement.name}</strong>
              <span>
                {workflowName(workflowTemplateIdFromInstance(engagementConfig(engagement)), workflowTemplates)} · v{engagement.version}
              </span>
            </div>
            <div className="row-actions">
              <Link className="button-link" to={`/engagements/${engagement.id}/outputs`}>
                运行应用
              </Link>
              <Link className="button-link secondary-button" to={`/engagements/new?engagement=${engagement.id}`}>
                继续配置
              </Link>
              {canManageEngagements ? (
                <button
                  type="button"
                  className="secondary-button"
                  disabled={cloningId === engagement.id}
                  onClick={() => void handleClone(engagement)}
                >
                  {cloningId === engagement.id ? "复制中…" : "复制并配置"}
                </button>
              ) : null}
              {canManageEngagements ? (
                <button
                  type="button"
                  className="secondary-button"
                  disabled={deletingId === engagement.id}
                  onClick={() => handleDelete(engagement)}
                >
                  {deletingId === engagement.id ? "删除中…" : "删除"}
                </button>
              ) : null}
            </div>
          </SectionCard>
        ))}
      </div>
      {engagements.length > 0 && filteredEngagements.length === 0 ? (
        <p className="muted">未找到包含「{searchQuery.trim()}」的应用。</p>
      ) : null}
      {engagements.length === 0 ? (
        <p className="muted">
          暂无任务，请先在「{ENGAGEMENT_LABELS.createNav}」中新建。
        </p>
      ) : null}
    </div>
  );
}
