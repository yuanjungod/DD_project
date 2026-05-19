import { useEffect, useState } from "react";
import { Link, NavLink, useParams } from "react-router-dom";

import {
  continueStepGated,
  deleteProjectAgentOverride,
  getAgentStepOutputFolder,
  getRun,
  listDiligenceSessions,
  listProjectAgentOverrides,
  listProjectRuns,
  listProjects,
  listResources,
  listWorkflowTemplates,
  listStepReviewChatTurns,
  postStepReviewChat,
  startRun,
  upsertProjectAgentOverride,
} from "../api/client";
import { ProjectResourcesPanel } from "../components/ProjectResourcesPanel";
import { SectionCard } from "../components/SectionCard";
import { workflowName } from "../data/workflows";
import { resolveGraphAgentOrder } from "../domain/workflowGraph";
import type {
  AgentRun,
  AgentStep,
  AgentStepOutputFolder,
  DiligenceSessionModel,
  Project,
  ProjectAgentOverride,
  Resource,
  StepReviewChatTurn,
  WorkflowTemplate,
} from "../types/domain";
import { formatApiDateTimeLocal } from "../utils/apiTime";

/** Backend may set raw_result.error (dispatch/HTTP errors); agent workflow failures often only have step.summary. */
function deriveRunFailureDetail(run: AgentRun | null | undefined): string {
  if (!run || run.status !== "failed") return "";
  const raw = run.raw_result;
  if (raw && typeof raw === "object" && "error" in raw && raw.error != null) {
    const msg = String(raw.error).trim();
    if (msg) return msg;
  }
  const failed = [...(run.steps ?? [])].filter((s) => s.status === "failed");
  failed.sort((a, b) => a.id.localeCompare(b.id));
  const tail = failed[failed.length - 1];
  if (tail?.summary?.trim()) return tail.summary.trim();
  return "";
}

function stepOutputDir(step: AgentStep): string {
  const result = step.result;
  return typeof result?.output_dir === "string" ? result.output_dir : "";
}

function jsonPreview(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

type OutputFileEntry = {
  id: string;
  label: string;
  path: string;
  content: string;
};

function outputFileEntries(folder: AgentStepOutputFolder): OutputFileEntry[] {
  if (!folder.available) {
    return [];
  }
  const entries: OutputFileEntry[] = [];
  if (folder.readme) {
    entries.push({
      id: "README.md",
      label: "README.md",
      path: folder.readme_path ?? "README.md",
      content: folder.readme,
    });
  }
  if (folder.result) {
    entries.push({
      id: "result.json",
      label: "result.json",
      path: `${folder.folder_path ?? ""}/result.json`,
      content: jsonPreview(folder.result),
    });
  }
  if (folder.resources) {
    entries.push({
      id: "resources/index.json",
      label: "resources/index.json",
      path: `${folder.folder_path ?? ""}/resources/index.json`,
      content: jsonPreview(folder.resources),
    });
  }
  for (const finding of folder.findings ?? []) {
    entries.push({
      id: `findings/${finding.name}`,
      label: `findings/${finding.name}`,
      path: finding.path,
      content: finding.content,
    });
  }
  return entries;
}

function AgentOutputFolderPanel({
  folder,
  loading,
  fallbackPath,
  selectedFileId,
  onSelectFile,
}: {
  folder?: AgentStepOutputFolder;
  loading: boolean;
  fallbackPath: string;
  selectedFileId?: string;
  onSelectFile: (fileId: string) => void;
}) {
  if (loading && !folder) {
    return <p className="muted">正在读取输出文件夹…</p>;
  }
  if (!folder) {
    return <p className="muted">输出目录：{fallbackPath}</p>;
  }
  if (!folder.available) {
    return (
      <div className="agent-output-folder">
        <strong>输出目录</strong>
        <code>{folder.folder_path ?? fallbackPath}</code>
        <p className="muted">{folder.reason ?? "输出文件夹暂不可读"}</p>
      </div>
    );
  }
  const entries = outputFileEntries(folder);
  const selected = entries.find((entry) => entry.id === selectedFileId);
  return (
    <div className="agent-output-folder">
      <strong>输出文件夹索引</strong>
      <div className="agent-output-folder__path">
        <span>目录</span>
        <code>{folder.folder_path}</code>
      </div>
      <div className="agent-output-folder__index" aria-label="输出目录文件索引">
        {entries.map((entry) => (
          <button
            key={entry.id}
            type="button"
            className={entry.id === selectedFileId ? "selected" : ""}
            onClick={() => onSelectFile(entry.id)}
          >
            {entry.label}
          </button>
        ))}
      </div>
      {selected ? (
        <div className="agent-output-folder__preview">
          <div className="agent-output-folder__path">
            <span>当前文件</span>
            <code>{selected.path}</code>
          </div>
          <pre>{selected.content}</pre>
        </div>
      ) : (
        <p className="muted">点击上方目录文件查看内容。</p>
      )}
    </div>
  );
}

export type ProjectDetailSection = "overview" | "resources" | "outputs" | "runs";

function appSectionPath(projectId: string, section: ProjectDetailSection): string {
  if (section === "overview") return `/projects/${encodeURIComponent(projectId)}`;
  return `/projects/${encodeURIComponent(projectId)}/${section}`;
}

function ProjectAppNav({ projectId }: { projectId: string }) {
  const items: Array<{ section: ProjectDetailSection; label: string; hint: string }> = [
    { section: "overview", label: "应用概览", hint: "标的与入口" },
    { section: "resources", label: "资源与 Agent 配置", hint: "按应用配置资源" },
    { section: "outputs", label: "模型运行输出", hint: "步骤与输出目录" },
    { section: "runs", label: "历史 Run", hint: "本应用记录" },
  ];
  return (
    <nav className="app-section-nav" aria-label="场景应用页面">
      {items.map((item) => (
        <NavLink key={item.section} to={appSectionPath(projectId, item.section)} end={item.section === "overview"}>
          <strong>{item.label}</strong>
          <span>{item.hint}</span>
        </NavLink>
      ))}
    </nav>
  );
}

function workflowAgentIds(project: Project | null, workflowTemplates: WorkflowTemplate[]): string[] {
  const workflowId = project?.company_config.scope.workflow_template_id ?? project?.company_config.scope.workflow_id;
  const workflow = workflowTemplates.find((item) => item.id === workflowId);
  return resolveGraphAgentOrder(workflow?.graph);
}

function splitFileIds(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  if (typeof value === "string") return value.split(/[\n,]/).map((item) => item.trim()).filter(Boolean);
  return [];
}

function splitIds(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function idsText(value: string[]): string {
  return (value ?? []).join(", ");
}

function emptyOverride(agentId: string): ProjectAgentOverride {
  return {
    agent_id: agentId,
    prompt_append: "",
    prompt_override: "",
    skill_package_ids_add: [],
    skill_package_ids_remove: [],
    tool_ids_add: [],
    tool_ids_remove: [],
    resource_ids_add: [],
    resource_ids_remove: [],
    platform_upload_file_ids: [],
    react_config_override: {},
    enabled: true,
  };
}

function AgentOverrideEditor({
  projectId,
  agentId,
  override,
  onRefresh,
}: {
  projectId: string;
  agentId: string;
  override?: ProjectAgentOverride;
  onRefresh: () => Promise<void>;
}) {
  const effective = override ?? emptyOverride(agentId);
  const [draft, setDraft] = useState<ProjectAgentOverride>(effective);
  const [saving, setSaving] = useState(false);
  const [localError, setLocalError] = useState("");

  useEffect(() => {
    setDraft(effective);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset editor when server override changes
  }, [agentId, JSON.stringify(override ?? {})]);

  async function save() {
    setSaving(true);
    setLocalError("");
    try {
      await upsertProjectAgentOverride(projectId, agentId, { ...draft, agent_id: agentId });
      await onRefresh();
    } catch (err: unknown) {
      setLocalError(String(err));
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!override) return;
    setSaving(true);
    setLocalError("");
    try {
      await deleteProjectAgentOverride(projectId, agentId);
      await onRefresh();
    } catch (err: unknown) {
      setLocalError(String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="agent-override-card">
      <div className="agent-override-card__header">
        <div>
          <strong>{agentId}</strong>
          <p className="muted">
            {override ? "已配置应用级覆盖；启动新 run 时会合成到快照。" : "继承场景模板配置，尚未配置应用级覆盖。"}
          </p>
        </div>
        <label className="agent-override-enabled">
          <input
            type="checkbox"
            checked={draft.enabled}
            onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })}
            disabled={saving}
          />
          启用覆盖
        </label>
      </div>
      {localError ? <div className="error">{localError}</div> : null}
      <label>
        追加提示词（继承模板后追加）
        <textarea
          rows={3}
          value={draft.prompt_append}
          onChange={(event) => setDraft({ ...draft, prompt_append: event.target.value })}
          disabled={saving}
        />
      </label>
      <label>
        覆盖提示词（填写后替代模板 prompt）
        <textarea
          rows={3}
          value={draft.prompt_override}
          onChange={(event) => setDraft({ ...draft, prompt_override: event.target.value })}
          disabled={saving}
        />
      </label>
      <div className="grid two">
        <label>
          追加 Skill IDs
          <input
            value={idsText(draft.skill_package_ids_add)}
            onChange={(event) => setDraft({ ...draft, skill_package_ids_add: splitIds(event.target.value) })}
            placeholder="skill_x, skill_y"
            disabled={saving}
          />
        </label>
        <label>
          移除模板 Skill IDs
          <input
            value={idsText(draft.skill_package_ids_remove)}
            onChange={(event) => setDraft({ ...draft, skill_package_ids_remove: splitIds(event.target.value) })}
            disabled={saving}
          />
        </label>
      </div>
      <div className="grid two">
        <label>
          追加工具 IDs
          <input
            value={idsText(draft.tool_ids_add)}
            onChange={(event) => setDraft({ ...draft, tool_ids_add: splitIds(event.target.value) })}
            placeholder="search, file_reader"
            disabled={saving}
          />
        </label>
        <label>
          移除模板工具 IDs
          <input
            value={idsText(draft.tool_ids_remove)}
            onChange={(event) => setDraft({ ...draft, tool_ids_remove: splitIds(event.target.value) })}
            disabled={saving}
          />
        </label>
      </div>
      <div className="grid two">
        <label>
          追加资源配置 IDs
          <input
            value={idsText(draft.resource_ids_add)}
            onChange={(event) => setDraft({ ...draft, resource_ids_add: splitIds(event.target.value) })}
            placeholder="resource_uploaded_files"
            disabled={saving}
          />
        </label>
        <label>
          移除模板资源配置 IDs
          <input
            value={idsText(draft.resource_ids_remove)}
            onChange={(event) => setDraft({ ...draft, resource_ids_remove: splitIds(event.target.value) })}
            disabled={saving}
          />
        </label>
      </div>
      <label>
        本应用限定可见 file_id（逗号或换行分隔）
        <textarea
          rows={2}
          value={idsText(draft.platform_upload_file_ids)}
          onChange={(event) => setDraft({ ...draft, platform_upload_file_ids: splitIds(event.target.value) })}
          disabled={saving}
        />
      </label>
      <div className="inline-form" style={{ flexWrap: "wrap" }}>
        <button type="button" onClick={() => void save()} disabled={saving}>
          {saving ? "保存中…" : "保存应用级配置"}
        </button>
        <button type="button" className="secondary-button" onClick={() => void remove()} disabled={saving || !override}>
          删除覆盖，恢复继承模板
        </button>
      </div>
    </div>
  );
}

function AgentResourceScopePanel({ agentIds, resources }: { agentIds: string[]; resources: Resource[] }) {
  const scopes = resources.filter((item) => item.type === "agent_resource_scope");
  return (
    <div className="agent-resource-grid">
      {agentIds.map((agentId) => {
        const scope = scopes.find((item) => item.value === agentId);
        const fileIds = splitFileIds(scope?.metadata_json?.uploaded_file_ids);
        return (
          <div key={agentId} className="agent-resource-card">
            <strong>{agentId}</strong>
            <p className="muted">
              {scope
                ? fileIds.length
                  ? `本应用限制 ${fileIds.length} 个 file_id 可见`
                  : "已登记本应用作用域备注，未限制 file_id"
                : "未配置专属作用域，默认使用工作流 Agent 模板与应用资源合并后的可见范围。"}
            </p>
            {fileIds.length ? (
              <div className="tag-row">
                {fileIds.map((fileId) => (
                  <span key={fileId}>{fileId}</span>
                ))}
              </div>
            ) : null}
          </div>
        );
      })}
      {agentIds.length === 0 ? <p className="muted">当前应用尚未解析到工作流 Agent。</p> : null}
    </div>
  );
}

export function ProjectDetailPage({ section = "overview" }: { section?: ProjectDetailSection }) {
  const { projectId = "" } = useParams();
  const [project, setProject] = useState<Project | null>(null);
  const [resources, setResources] = useState<Resource[]>([]);
  const [agentOverrides, setAgentOverrides] = useState<ProjectAgentOverride[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [workflowTemplates, setWorkflowTemplates] = useState<WorkflowTemplate[]>([]);
  const [sessions, setSessions] = useState<DiligenceSessionModel[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [activeRun, setActiveRun] = useState<AgentRun | null>(null);
  const [error, setError] = useState("");
  const [runStarting, setRunStarting] = useState(false);
  const [continueLoading, setContinueLoading] = useState(false);
  const [stepGatedMode, setStepGatedMode] = useState(false);
  const [reviewChatDraft, setReviewChatDraft] = useState("");
  const [reviewChatSending, setReviewChatSending] = useState(false);
  const [reviewChatByStep, setReviewChatByStep] = useState<Record<string, StepReviewChatTurn[]>>({});
  const [outputFoldersByStep, setOutputFoldersByStep] = useState<Record<string, AgentStepOutputFolder>>({});
  const [loadingOutputStepIds, setLoadingOutputStepIds] = useState<Record<string, boolean>>({});
  const [selectedOutputFileByStep, setSelectedOutputFileByStep] = useState<Record<string, string>>({});
  const [pollingRunId, setPollingRunId] = useState<string | null>(null);

  async function refresh() {
    const [projects, resourceItems, overrideItems, runItems, sessionItems, workflowItems] = await Promise.all([
      listProjects(),
      listResources(projectId),
      listProjectAgentOverrides(projectId),
      listProjectRuns(projectId),
      listDiligenceSessions(projectId),
      listWorkflowTemplates(),
    ]);
    setProject(projects.find((item) => item.id === projectId) ?? null);
    setResources(resourceItems);
    setAgentOverrides(overrideItems);
    setRuns(runItems);
    setWorkflowTemplates(workflowItems);
    setSessions(sessionItems);
    setActiveRun((prev) => {
      if (prev?.id) {
        const match = runItems.find((r) => r.id === prev.id);
        if (match) return match;
      }
      return runItems[0] ?? null;
    });
  }

  useEffect(() => {
    setPollingRunId(null);
    setRunStarting(false);
    setContinueLoading(false);
    setStepGatedMode(false);
    setReviewChatByStep({});
    setOutputFoldersByStep({});
    setLoadingOutputStepIds({});
    setSelectedOutputFileByStep({});
    setReviewChatDraft("");
  }, [projectId]);

  useEffect(() => {
    if (!projectId) return;
    refresh().catch((err: unknown) => setError(String(err)));
  }, [projectId]);

  useEffect(() => {
    setSelectedSessionId((prev) => {
      if (prev && sessions.some((s) => s.id === prev)) return prev;
      return sessions[0]?.id ?? "";
    });
  }, [sessions]);

  useEffect(() => {
    if (!pollingRunId) return;
    const id = pollingRunId;

    async function tick() {
      try {
        const latest = await getRun(id);
        setActiveRun(latest);
        const runItems = await listProjectRuns(projectId);
        setRuns(runItems);
        if (latest.status === "completed" || latest.status === "failed" || latest.status === "paused") {
          setPollingRunId(null);
          setRunStarting(false);
          await refresh();
        }
      } catch (err: unknown) {
        setPollingRunId(null);
        setRunStarting(false);
        setError(String(err));
      }
    }

    void tick();
    const interval = window.setInterval(() => void tick(), 2000);
    return () => window.clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh intentionally stable per navigation (projectId)
  }, [pollingRunId, projectId]);

  useEffect(() => {
    const runId = activeRun?.id;
    const stepId =
      activeRun?.status === "paused"
        ? [...(activeRun.steps ?? [])]
            .sort((a, b) => a.id.localeCompare(b.id))
            .filter((s) => s.status === "completed")
            .slice(-1)[0]?.id
        : undefined;
    if (!runId || !stepId) return;
    let cancelled = false;
    listStepReviewChatTurns(runId, stepId)
      .then((turns) => {
        if (!cancelled) {
          setReviewChatByStep((prev) => ({ ...prev, [stepId]: turns }));
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [activeRun?.id, activeRun?.status, activeRun?.steps]);

  useEffect(() => {
    const runId = activeRun?.id;
    if (!runId) return;
    for (const step of activeRun.steps ?? []) {
      const outputDir = stepOutputDir(step);
      if (!outputDir || loadingOutputStepIds[step.id]) {
        continue;
      }
      const existing = outputFoldersByStep[step.id];
      if (existing && (existing.folder_path === outputDir || existing.reason)) {
        continue;
      }
      setLoadingOutputStepIds((prev) => ({ ...prev, [step.id]: true }));
      getAgentStepOutputFolder(runId, step.id)
        .then((folder) => {
          setOutputFoldersByStep((prev) => ({ ...prev, [step.id]: folder }));
        })
        .catch((err: unknown) => {
          setOutputFoldersByStep((prev) => ({
            ...prev,
            [step.id]: { available: false, step_id: step.id, agent: step.agent, reason: String(err) },
          }));
        })
        .finally(() => {
          setLoadingOutputStepIds((prev) => ({ ...prev, [step.id]: false }));
        });
    }
  }, [activeRun?.id, activeRun?.steps, loadingOutputStepIds, outputFoldersByStep]);

  async function handleStartRun(mode: "new" | "continue") {
    setRunStarting(true);
    setError("");
    try {
      const base =
        mode === "continue" && selectedSessionId.trim()
          ? { session_mode: "continue" as const, diligence_session_id: selectedSessionId.trim() }
          : { session_mode: "new" as const };
      const started = await startRun(projectId, {
        ...base,
        ...(stepGatedMode ? { interaction_mode: "step_gated" as const } : {}),
      });
      setActiveRun(started);
      await refresh();
      if (started.status === "running" || started.status === "pending") {
        setPollingRunId(started.id);
      } else {
        setRunStarting(false);
      }
    } catch (err) {
      setError(String(err));
      setRunStarting(false);
    }
  }

  async function handleSendReviewChat() {
    if (!activeRun || pausedReviewStep == null || !reviewChatDraft.trim()) return;
    setReviewChatSending(true);
    setError("");
    try {
      const out = await postStepReviewChat(activeRun.id, pausedReviewStep.id, reviewChatDraft.trim());
      setReviewChatByStep((prev) => ({ ...prev, [pausedReviewStep!.id]: out.turns }));
      setReviewChatDraft("");
    } catch (err: unknown) {
      setError(String(err));
    } finally {
      setReviewChatSending(false);
    }
  }

  async function handleContinueStepGated() {
    if (!activeRun?.id || activeRun.status !== "paused") return;
    setContinueLoading(true);
    setError("");
    try {
      await continueStepGated(activeRun.id);
      await refresh();
      const id = activeRun.id;
      setPollingRunId(id);
    } catch (err: unknown) {
      setError(String(err));
    } finally {
      setContinueLoading(false);
    }
  }

  const runErr = deriveRunFailureDetail(activeRun);

  const runInFlight =
    Boolean(pollingRunId) || activeRun?.status === "running" || runStarting || continueLoading;
  const awaitingStepReview = activeRun?.status === "paused";
  const orderedSteps = [...(activeRun?.steps ?? [])].sort((a, b) => a.id.localeCompare(b.id));
  const pausedReviewStep = awaitingStepReview
    ? [...orderedSteps].filter((s) => s.status === "completed").slice(-1)[0]
    : undefined;
  const projectWorkflowName = project
    ? workflowName(
        project.company_config.scope.workflow_template_id ?? project.company_config.scope.workflow_id,
        workflowTemplates,
      )
    : "";
  const appAgentIds = workflowAgentIds(project, workflowTemplates);

  return (
    <div className="page-stack">
      <header className="page-hero action-hero action-hero--align-start">
        <div>
          <p className="eyebrow">Application Detail</p>
          <h1>{project?.company_config.target_company.name ?? "尽调应用"}</h1>
          <p>
            {project
              ? `${projectWorkflowName} · v${project.company_config.scope.workflow_template_version ?? 1}`
              : "加载中"}
          </p>
        </div>
        {section === "outputs" ? (
        <div className="hero-run-controls" aria-label="运行 diligence">
          <div className="hero-run-controls__primary-row">
            <div className="hero-run-controls__session-field">
              <span id="hero-session-caption" className="muted hero-run-controls__caption">
                当前 diligence session
              </span>
              <select
                aria-labelledby="hero-session-caption"
                value={selectedSessionId}
                onChange={(event) => setSelectedSessionId(event.target.value)}
                disabled={runStarting || sessions.length === 0}
              >
                {sessions.length === 0 ? (
                  <option value="">暂无 session（请先新起）</option>
                ) : null}
                {sessions.map((session) => (
                  <option key={session.id} value={session.id}>
                    {session.id} · {session.runs.length} 次
                  </option>
                ))}
              </select>
            </div>
            <div className="hero-run-controls__buttons">
              <button type="button" onClick={() => void handleStartRun("new")} disabled={runStarting}>
                {runStarting ? "启动中…" : "新 Session 跑一趟"}
              </button>
              <button
                type="button"
                onClick={() => void handleStartRun("continue")}
                disabled={runStarting || !selectedSessionId}
              >
                本 Session 再跑一趟
              </button>
            </div>
          </div>
          <label className="hero-run-controls__stepgate">
            <input
              type="checkbox"
              checked={stepGatedMode}
              onChange={(e) => setStepGatedMode(e.target.checked)}
              disabled={runInFlight}
            />
            <span className="hero-run-controls__stepgate-copy">
              <span className="hero-run-controls__stepgate-title">每步完成后暂停</span>
              <span className="hero-run-controls__stepgate-desc muted">
                便于与 Agent 对话、核对结果后再继续下一步
              </span>
            </span>
          </label>
        </div>
        ) : null}
      </header>
      <ProjectAppNav projectId={projectId} />
      {error ? <div className="error">{error}</div> : null}
      {section === "overview" ? (
        <div className="grid three">
          <SectionCard
            title="资源与 Agent 配置"
            description="按应用维护文件、来源、线索、指标，并可为本应用里的具体 Agent 登记资源作用域。"
          >
            <p className="muted">
              已登记资源 {resources.length} 条 · 工作流 Agent {appAgentIds.length} 个
            </p>
            <Link className="button-link" to={appSectionPath(projectId, "resources")}>
              配置资源
            </Link>
          </SectionCard>
          <SectionCard title="模型运行输出" description="启动 Run、查看每个 Agent 的步骤状态、输出目录、README 与 findings。">
            <p className="muted">
              当前 Run：{activeRun ? `${activeRun.id} · ${activeRun.status}` : "暂无"}
            </p>
            <Link className="button-link" to={appSectionPath(projectId, "outputs")}>
              查看输出
            </Link>
          </SectionCard>
          <SectionCard title="本应用历史 Run" description="按 session 与 attempt 查看本应用历史执行记录。">
            <p className="muted">历史 Run {runs.length} 条 · Session {sessions.length} 个</p>
            <Link className="button-link" to={appSectionPath(projectId, "runs")}>
              查看历史
            </Link>
          </SectionCard>
        </div>
      ) : null}
      {section === "resources" ? (
      <div className="page-stack">
        <div className="grid two">
          <SectionCard
            title="应用资源管理"
            description="上传文件材料、配置可信/屏蔽来源、竞品、文件引用（手动 ID）、线索与指标等。启动 Run 时会并入 company_config 供 Agent 使用。"
          >
            <ProjectResourcesPanel projectId={projectId} resources={resources} onRefresh={() => refresh()} />
          </SectionCard>
          <SectionCard
            title="本应用 Agent 资源作用域"
            description="用资源类型「Agent 资源作用域」为具体 Agent 填 file_id 列表；运行时 file_reader 会按当前 Agent 过滤可见文件。"
          >
            <AgentResourceScopePanel agentIds={appAgentIds} resources={resources} />
          </SectionCard>
        </div>
        <SectionCard
          title="本应用 Agent 覆盖配置"
          description="这里配置的是应用级 overlay：提示词、Skills、工具、资源配置和文件作用域只影响本应用未来新 run 的 snapshot，不会覆盖场景模板。"
        >
          <div className="agent-override-list">
            {appAgentIds.map((agentId) => (
              <AgentOverrideEditor
                key={agentId}
                projectId={projectId}
                agentId={agentId}
                override={agentOverrides.find((item) => item.agent_id === agentId)}
                onRefresh={refresh}
              />
            ))}
            {appAgentIds.length === 0 ? <p className="muted">当前应用尚未解析到工作流 Agent。</p> : null}
          </div>
        </SectionCard>
      </div>
      ) : null}
      {section === "runs" ? (
        <SectionCard title="本应用历史 Run" description="这里只保留本应用的历史执行记录，模型输出文件请到「模型运行输出」页查看。">
          <ul className="list">
            {runs.map((run) => (
              <li key={run.id}>
                <span>{run.status}</span>
                <strong>{run.id}</strong>
                <p className="muted">
                  session {run.session_id ?? "—"} · attempt {run.attempt_index ?? 1}
                </p>
                <p>{formatApiDateTimeLocal(run.started_at)}</p>
              </li>
            ))}
          </ul>
          {runs.length === 0 && !runStarting ? (
            <p className="muted">尚无 Run。点击右上角启动后即可在此看到记录。</p>
          ) : null}
        </SectionCard>
      ) : null}
      {section === "outputs" ? (
      <SectionCard title="Agent 输出目录" description="每个 Agent 完成后会生成输出文件夹，可在对应步骤下查看 README、findings 与资源索引。">
          {activeRun?.status === "paused" ? (
            <p className="notice">
              已进入「分步门禁」暂停点：可先与<strong>最新完成步骤</strong>对应 Agent 在下方复核对话中沟通，确认后点击「继续下一步」拉起后续链路。
            </p>
          ) : null}
          {activeRun?.status === "failed" ? (
            <>
              <p className="error">{runErr || "Run 失败"}</p>
              <p className="notice">
                每次调用都会走完整 Agent 链；「本 Session 再跑」会把上一轮 attempt 的摘要注入首个 Agent 的提示词。若需全新上下文，请用「新 Session
                跑一趟」。修好 Agent 服务后也可使用 Run 级重试。
              </p>
            </>
          ) : null}
          {orderedSteps.length ? (
            <ol className="timeline">
              {orderedSteps.map((step) => (
                <li key={step.id}>
                  <span className={`status ${step.status}`}>{step.status}</span>
                  <strong>{step.agent}</strong>
                  <p>{step.summary || (step.status === "running" ? "执行中…" : "")}</p>
                  {stepOutputDir(step) ? (
                    <AgentOutputFolderPanel
                      folder={outputFoldersByStep[step.id]}
                      loading={Boolean(loadingOutputStepIds[step.id])}
                      fallbackPath={stepOutputDir(step)}
                      selectedFileId={selectedOutputFileByStep[step.id]}
                      onSelectFile={(fileId) =>
                        setSelectedOutputFileByStep((prev) => ({
                          ...prev,
                          [step.id]: fileId,
                        }))
                      }
                    />
                  ) : step.status === "completed" ? (
                    <p className="muted">输出文件夹正在生成或等待下一次轮询刷新。</p>
                  ) : null}
                  {pausedReviewStep?.id === step.id && activeRun?.id ? (
                    <div className="step-review-panel">
                      <h4>本步复核对话</h4>
                      <p className="muted">复核对象：{step.agent} 的当前输出目录与所选文件。</p>
                      <div className="review-chat-turns">
                        {(reviewChatByStep[step.id] ?? []).map((t) => (
                          <div key={t.id} className={`review-chat-msg ${t.role}`}>
                            <span className="muted">{t.role}</span>
                            <p>{t.content}</p>
                          </div>
                        ))}
                      </div>
                      <div className="inline-form" style={{ marginTop: "0.75rem", flexWrap: "wrap", alignItems: "flex-start" }}>
                        <textarea
                          rows={3}
                          style={{ minWidth: "min(100%, 28rem)", flex: 1 }}
                          placeholder="校验这个输出目录里的内容、纠错或追问…"
                          value={reviewChatDraft}
                          onChange={(e) => setReviewChatDraft(e.target.value)}
                          disabled={reviewChatSending}
                        />
                        <button
                          type="button"
                          onClick={() => void handleSendReviewChat()}
                          disabled={reviewChatSending || !reviewChatDraft.trim()}
                        >
                          {reviewChatSending ? "发送中…" : "发送至本步 Agent"}
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleContinueStepGated()}
                          disabled={continueLoading}
                        >
                          {continueLoading ? "继续执行中…" : "校验完成，继续下一步"}
                        </button>
                      </div>
                    </div>
                  ) : null}
                </li>
              ))}
            </ol>
          ) : runInFlight ? (
            <p className="muted">
              后台正在执行尽调链路。若 Agent 服务配置了 <code>PLATFORM_CALLBACK_BASE_URL</code> 指向本后端，步骤会逐步出现；否则需待全流程结束。
            </p>
          ) : (
            <p className="muted">启动 run 后展示各 agent 状态。</p>
          )}
          {runInFlight && orderedSteps.length ? (
            <p className="muted" style={{ marginTop: "0.75rem" }}>
              流程进行中；步骤与输出目录会随回调或轮询持续刷新。
            </p>
          ) : null}
      </SectionCard>
      ) : null}
    </div>
  );
}
