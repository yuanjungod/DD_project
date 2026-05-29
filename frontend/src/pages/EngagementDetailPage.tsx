import { useEffect, useState } from "react";
import { NavLink, useParams } from "react-router-dom";

import {
  continueStepGated,
  downloadAgentStepOutputFile,
  downloadAgentStepOutputFolder,
  getAgentStepOutputFile,
  getAgentStepOutputFolder,
  getRun,
  listEngagementRuns,
  listEngagements,
  listWorkflowSessions,
  listStepReviewChatTurns,
  listWorkflowTemplates,
  postStepReviewChat,
  startRun,
} from "../api/client";
import { SectionCard } from "../components/SectionCard";
import { workflowName } from "../data/workflows";
import { workflowTemplateIdFromConfig } from "../domain/companyConfig";
import { engagementConfig, engagementIdentityLabel } from "../domain/engagementIdentity";
import { resolveRunStatus, runStatusLabel, runStatusClassName } from "../domain/runStatus";
import type {
  AgentRun,
  AgentStep,
  AgentStepOutputFile,
  AgentStepOutputFolder,
  WorkflowSessionModel,
  Engagement,
  StepReviewChatTurn,
  WorkflowTemplate,
} from "../types/domain";
import { formatApiDateTimeLocal } from "../utils/apiTime";

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

type OutputFileEntry = {
  id: string;
  label: string;
  path: string;
  content: string;
  contentType: AgentStepOutputFile["content_type"];
  sizeBytes: number;
  truncated?: boolean;
  previewUnavailable?: boolean;
};

function formatOutputFileSize(sizeBytes: number): string {
  if (!Number.isFinite(sizeBytes) || sizeBytes < 0) return "—";
  if (sizeBytes < 1024) return `${sizeBytes} B`;
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`;
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

function shortFolderPath(fullPath: string): string {
  const parts = fullPath.split("/").filter(Boolean);
  if (parts.length <= 4) return fullPath;
  return `…/${parts.slice(-4).join("/")}`;
}

function outputFileEntries(folder: AgentStepOutputFolder): OutputFileEntry[] {
  if (!folder.available) return [];
  if (folder.files?.length) {
    return folder.files.map((file) => ({
      id: file.path,
      label: file.path,
      path: file.path,
      content: file.content ?? "",
      contentType: file.content_type,
      sizeBytes: file.size_bytes,
      truncated: file.truncated,
      previewUnavailable: file.preview_unavailable,
    }));
  }
  if (folder.readme) {
    return [
      {
        id: "README.md",
        label: "README.md",
        path: folder.readme_path ?? "README.md",
        content: folder.readme,
        contentType: "text",
        sizeBytes: folder.readme.length,
      },
    ];
  }
  return [];
}

function AgentOutputFolderPanel({
  runId,
  stepId,
  folder,
  loading,
  fallbackPath,
  selectedFileId,
  onSelectFile,
}: {
  runId: string;
  stepId: string;
  folder?: AgentStepOutputFolder;
  loading: boolean;
  fallbackPath: string;
  selectedFileId?: string;
  onSelectFile: (fileId: string) => void;
}) {
  const [previewByPath, setPreviewByPath] = useState<Record<string, OutputFileEntry>>({});
  const [previewLoadingPath, setPreviewLoadingPath] = useState("");
  const [exporting, setExporting] = useState(false);
  const [downloadingPath, setDownloadingPath] = useState("");
  const [actionError, setActionError] = useState("");

  const entries = folder ? outputFileEntries(folder) : [];
  const currentFileId = selectedFileId ?? entries[0]?.id;
  const activeEntry =
    currentFileId != null
      ? previewByPath[currentFileId] ?? entries.find((entry) => entry.id === currentFileId)
      : undefined;

  useEffect(() => {
    if (!folder?.available || !currentFileId) return;
    const entry = entries.find((item) => item.id === currentFileId);
    if (!entry) return;
    if (entry.contentType === "text" && entry.content) {
      setPreviewByPath((prev) => (prev[entry.id] ? prev : { ...prev, [entry.id]: entry }));
      return;
    }
    let cancelled = false;
    setPreviewLoadingPath(entry.path);
    setActionError("");
    getAgentStepOutputFile(runId, stepId, entry.path)
      .then((file) => {
        if (cancelled) return;
        setPreviewByPath((prev) => ({
          ...prev,
          [file.path]: {
            id: file.path,
            label: file.path,
            path: file.path,
            content: file.content ?? "",
            contentType: file.content_type,
            sizeBytes: file.size_bytes,
            truncated: file.truncated,
            previewUnavailable: file.preview_unavailable,
          },
        }));
      })
      .catch((err: unknown) => {
        if (!cancelled) setActionError(String(err));
      })
      .finally(() => {
        if (!cancelled) setPreviewLoadingPath("");
      });
    return () => {
      cancelled = true;
    };
  }, [currentFileId, entries, folder, runId, stepId]);

  async function handleExportFolder() {
    setExporting(true);
    setActionError("");
    try {
      const folderName = folder?.folder_path?.split("/").filter(Boolean).slice(-1)[0] ?? folder?.agent ?? "agent-output";
      await downloadAgentStepOutputFolder(runId, stepId, folderName);
    } catch (err: unknown) {
      setActionError(String(err));
    } finally {
      setExporting(false);
    }
  }

  async function handleDownloadFile(filePath: string, fileName: string) {
    setDownloadingPath(filePath);
    setActionError("");
    try {
      await downloadAgentStepOutputFile(runId, stepId, filePath, fileName);
    } catch (err: unknown) {
      setActionError(String(err));
    } finally {
      setDownloadingPath("");
    }
  }

  if (loading && !folder) {
    return <p className="muted">正在读取输出文件夹…</p>;
  }
  if (!folder) return <p className="muted">输出目录：{fallbackPath}</p>;
  if (!folder.available) {
    return (
      <div className="agent-output-viewer agent-output-viewer--unavailable">
        <p className="muted">{folder.reason ?? "输出文件夹暂不可读"}</p>
        <code title={folder.folder_path ?? fallbackPath}>{folder.folder_path ?? fallbackPath}</code>
      </div>
    );
  }

  return (
    <div className="agent-output-viewer">
      <div className="agent-output-viewer__controls">
        <label className="agent-output-viewer__select-field">
          <span>选择文件</span>
          <select
            value={currentFileId ?? ""}
            onChange={(event) => onSelectFile(event.target.value)}
            disabled={entries.length === 0}
          >
            {entries.length === 0 ? <option value="">暂无文件</option> : null}
            {entries.map((entry) => (
              <option key={entry.id} value={entry.id}>
                {entry.path} ({formatOutputFileSize(entry.sizeBytes)})
              </option>
            ))}
          </select>
        </label>
        <div className="agent-output-viewer__actions">
          <button
            type="button"
            className="secondary-button"
            onClick={() =>
              activeEntry
                ? void handleDownloadFile(
                    activeEntry.path,
                    activeEntry.path.split("/").pop() ?? activeEntry.path,
                  )
                : undefined
            }
            disabled={!activeEntry || downloadingPath === activeEntry.path}
          >
            {activeEntry && downloadingPath === activeEntry.path ? "下载中…" : "下载当前文件"}
          </button>
          <button
            type="button"
            className="secondary-button"
            onClick={() => void handleExportFolder()}
            disabled={exporting || entries.length === 0}
          >
            {exporting ? "导出中…" : "导出 ZIP"}
          </button>
        </div>
      </div>

      <p className="agent-output-viewer__path muted" title={folder.folder_path}>
        目录：<code>{shortFolderPath(folder.folder_path ?? "")}</code>
      </p>

      {actionError ? <p className="error">{actionError}</p> : null}

      <div
        className={`agent-output-viewer__content ${
          activeEntry?.path.toLowerCase().endsWith(".md") ? "is-markdown" : ""
        }`}
      >
        {!activeEntry ? (
          <p className="muted agent-output-viewer__placeholder">请选择要查看的文件。</p>
        ) : previewLoadingPath === activeEntry.path ? (
          <p className="muted agent-output-viewer__placeholder">正在加载文件内容…</p>
        ) : activeEntry.contentType === "text" && activeEntry.content ? (
          <pre>{activeEntry.content}</pre>
        ) : activeEntry.contentType === "binary" || activeEntry.previewUnavailable ? (
          <p className="muted agent-output-viewer__placeholder">该文件不支持在线预览，请下载后查看。</p>
        ) : (
          <p className="muted agent-output-viewer__placeholder">暂无预览内容。</p>
        )}
      </div>

      {activeEntry?.truncated ? <p className="muted agent-output-viewer__hint">预览内容已截断，完整内容请下载文件。</p> : null}
    </div>
  );
}

export type EngagementDetailSection = "outputs" | "runs";

function appSectionPath(engagementId: string, section: EngagementDetailSection): string {
  return `/engagements/${encodeURIComponent(engagementId)}/${section}`;
}

const SECTION_NAV: Array<{ section: EngagementDetailSection; label: string }> = [
  { section: "outputs", label: "运行" },
  { section: "runs", label: "历史" },
];

function EngagementAppNav({ engagementId }: { engagementId: string }) {
  return (
    <nav className="app-section-nav" aria-label="Engagement 分区">
      {SECTION_NAV.map((item) => (
        <NavLink key={item.section} to={appSectionPath(engagementId, item.section)} preventScrollReset>
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}

export function EngagementDetailPage({ section = "outputs" }: { section?: EngagementDetailSection }) {
  const { engagementId = "" } = useParams();
  const [engagement, setEngagement] = useState<Engagement | null>(null);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [workflowTemplates, setWorkflowTemplates] = useState<WorkflowTemplate[]>([]);
  const [sessions, setSessions] = useState<WorkflowSessionModel[]>([]);
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
    const [engagements, runItems, sessionItems, workflowItems] = await Promise.all([
      listEngagements(),
      listEngagementRuns(engagementId),
      listWorkflowSessions(engagementId),
      listWorkflowTemplates(),
    ]);
    setEngagement(engagements.find((item) => item.id === engagementId) ?? null);
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
  }, [engagementId]);

  useEffect(() => {
    if (!engagementId) return;
    refresh().catch((err: unknown) => setError(String(err)));
  }, [engagementId]);

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
        const runItems = await listEngagementRuns(engagementId);
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
  }, [pollingRunId, engagementId]);

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
        if (!cancelled) setReviewChatByStep((prev) => ({ ...prev, [stepId]: turns }));
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
      if (!outputDir || loadingOutputStepIds[step.id]) continue;
      const existing = outputFoldersByStep[step.id];
      if (existing && (existing.folder_path === outputDir || existing.reason)) continue;
      setLoadingOutputStepIds((prev) => ({ ...prev, [step.id]: true }));
      getAgentStepOutputFolder(runId, step.id)
        .then((folder) => {
          setOutputFoldersByStep((prev) => ({ ...prev, [step.id]: folder }));
          if (folder.available) {
            const defaultFile = folder.files?.[0]?.path ?? (folder.readme ? "README.md" : "");
            if (defaultFile) {
              setSelectedOutputFileByStep((prev) => (prev[step.id] ? prev : { ...prev, [step.id]: defaultFile }));
            }
          }
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
          ? { session_mode: "continue" as const, workflow_session_id: selectedSessionId.trim() }
          : { session_mode: "new" as const };
      const started = await startRun(engagementId, {
        ...base,
        ...(stepGatedMode ? { interaction_mode: "step_gated" as const } : {}),
      });
      setActiveRun(started);
      await refresh();
      if (started.status === "running" || started.status === "pending") setPollingRunId(started.id);
      else setRunStarting(false);
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
      setReviewChatByStep((prev) => ({ ...prev, [pausedReviewStep.id]: out.turns }));
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
      setPollingRunId(activeRun.id);
    } catch (err: unknown) {
      setError(String(err));
    } finally {
      setContinueLoading(false);
    }
  }

  const runErr = deriveRunFailureDetail(activeRun);
  const runInFlight = Boolean(pollingRunId) || activeRun?.status === "running" || runStarting || continueLoading;
  const awaitingStepReview = activeRun?.status === "paused";
  const orderedSteps = [...(activeRun?.steps ?? [])].sort((a, b) => a.id.localeCompare(b.id));
  const pausedReviewStep = awaitingStepReview ? [...orderedSteps].filter((s) => s.status === "completed").slice(-1)[0] : undefined;
  const engagementWorkflowName = engagement
    ? workflowName(workflowTemplateIdFromConfig(engagementConfig(engagement)), workflowTemplates)
    : "";

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Engagement</p>
        <h1>{engagement ? engagementIdentityLabel(engagement) : "Engagement"}</h1>
        <p>
          {engagement ? (
            <>
              {engagementWorkflowName} · 应用 ID <code>{engagement.application_id}</code> · 技术 ID <code>{engagement.id}</code>
            </>
          ) : (
            "加载中"
          )}
        </p>
      </header>
      <EngagementAppNav engagementId={engagementId} />
      {error ? <div className="error">{error}</div> : null}
      {section === "runs" ? (
        <SectionCard title="当前 Engagement 历史 Run" description="按 session 与 attempt 查看当前 Engagement 历史执行记录；模型输出文件请到「运行」页查看。">
          <ul className="list">
            {runs.map((run) => (
              <li key={run.id}>
                <span className={`status ${runStatusClassName(run)}`}>{runStatusLabel(resolveRunStatus(run))}</span>
                <strong>{run.id}</strong>
                <p className="muted">session {run.session_id ?? "—"} · attempt {run.attempt_index ?? 1}</p>
                <p>{formatApiDateTimeLocal(run.started_at)}</p>
              </li>
            ))}
          </ul>
          {runs.length === 0 && !runStarting ? <p className="muted">尚无 Run。在「运行」页启动后即可在此看到记录。</p> : null}
        </SectionCard>
      ) : null}
      {section === "outputs" ? (
        <>
          <div className="run-controls-panel hero-run-controls" aria-label="运行 workflow">
            <div className="hero-run-controls__primary-row">
              <div className="hero-run-controls__session-field">
                <span id="run-session-caption" className="muted hero-run-controls__caption">
                  当前 workflow session
                </span>
                <select
                  aria-labelledby="run-session-caption"
                  value={selectedSessionId}
                  onChange={(event) => setSelectedSessionId(event.target.value)}
                  disabled={runStarting || sessions.length === 0}
                >
                  {sessions.length === 0 ? <option value="">暂无 session（请先新起）</option> : null}
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
                <button type="button" onClick={() => void handleStartRun("continue")} disabled={runStarting || !selectedSessionId}>
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
                <span className="hero-run-controls__stepgate-desc muted">便于与 Agent 对话、核对结果后再继续下一步</span>
              </span>
            </label>
          </div>
          <SectionCard title="Agent 输出目录" description="下拉选择文件查看内容，也可导出整个输出目录。">
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
                    <span className={`status ${step.status}`}>{runStatusLabel(step.status)}</span>
                    <strong>{step.agent}</strong>
                    <p>{step.summary || (step.status === "running" ? "执行中…" : "")}</p>
                    {stepOutputDir(step) && activeRun?.id ? (
                      <AgentOutputFolderPanel
                        runId={activeRun.id}
                        stepId={step.id}
                        folder={outputFoldersByStep[step.id]}
                        loading={Boolean(loadingOutputStepIds[step.id])}
                        fallbackPath={stepOutputDir(step)}
                        selectedFileId={selectedOutputFileByStep[step.id]}
                        onSelectFile={(fileId) => setSelectedOutputFileByStep((prev) => ({ ...prev, [step.id]: fileId }))}
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
                          <button type="button" onClick={() => void handleSendReviewChat()} disabled={reviewChatSending || !reviewChatDraft.trim()}>
                            {reviewChatSending ? "发送中…" : "发送至本步 Agent"}
                          </button>
                          <button type="button" onClick={() => void handleContinueStepGated()} disabled={continueLoading}>
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
        </>
      ) : null}
    </div>
  );
}
