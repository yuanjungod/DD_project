import { useEffect, useState } from "react";
import { NavLink, useParams } from "react-router-dom";

import {
  continueStepGated,
  getAgentStepOutputFolder,
  getRun,
  listDiligenceSessions,
  listProjectRuns,
  listProjects,
  listStepReviewChatTurns,
  listWorkflowTemplates,
  postStepReviewChat,
  startRun,
} from "../api/client";
import { SectionCard } from "../components/SectionCard";
import { workflowName } from "../data/workflows";
import { projectIdentityLabel } from "../domain/projectIdentity";
import type {
  AgentRun,
  AgentStep,
  AgentStepOutputFolder,
  DiligenceSessionModel,
  Project,
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

export type ProjectDetailSection = "outputs" | "runs";

function appSectionPath(projectId: string, section: ProjectDetailSection): string {
  return `/projects/${encodeURIComponent(projectId)}/${section}`;
}

const SECTION_NAV: Array<{ section: ProjectDetailSection; label: string }> = [
  { section: "outputs", label: "运行" },
  { section: "runs", label: "历史" },
];

function ProjectAppNav({ projectId }: { projectId: string }) {
  return (
    <nav className="app-section-nav" aria-label="场景应用分区">
      {SECTION_NAV.map((item) => (
        <NavLink key={item.section} to={appSectionPath(projectId, item.section)} preventScrollReset>
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}

const RUN_STATUS_LABELS: Record<string, string> = {
  completed: "已完成",
  failed: "失败",
  paused: "待复核",
  pending: "排队中",
  running: "运行中",
};

function runStatusLabel(status?: string | null): string {
  if (!status) return "暂无";
  return RUN_STATUS_LABELS[status] ?? status;
}

export function ProjectDetailPage({ section = "outputs" }: { section?: ProjectDetailSection }) {
  const { projectId = "" } = useParams();
  const [project, setProject] = useState<Project | null>(null);
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
    const [projects, runItems, sessionItems, workflowItems] = await Promise.all([
      listProjects(),
      listProjectRuns(projectId),
      listDiligenceSessions(projectId),
      listWorkflowTemplates(),
    ]);
    setProject(projects.find((item) => item.id === projectId) ?? null);
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

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">场景应用</p>
        <h1>{project ? projectIdentityLabel(project) : "尽调应用"}</h1>
        <p>
          {project ? (
            <>
              {projectWorkflowName} · 应用 ID <code>{project.application_id}</code> · 技术 ID <code>{project.id}</code>
            </>
          ) : (
            "加载中"
          )}
        </p>
      </header>
      <ProjectAppNav projectId={projectId} />
      {error ? <div className="error">{error}</div> : null}
      {section === "runs" ? (
        <SectionCard title="本应用历史 Run" description="按 session 与 attempt 查看本应用历史执行记录；模型输出文件请到「运行」页查看。">
          <ul className="list">
            {runs.map((run) => (
              <li key={run.id}>
                <span>{runStatusLabel(run.status)}</span>
                <strong>{run.id}</strong>
                <p className="muted">
                  session {run.session_id ?? "—"} · attempt {run.attempt_index ?? 1}
                </p>
                <p>{formatApiDateTimeLocal(run.started_at)}</p>
              </li>
            ))}
          </ul>
          {runs.length === 0 && !runStarting ? (
            <p className="muted">尚无 Run。在「运行」页启动后即可在此看到记录。</p>
          ) : null}
        </SectionCard>
      ) : null}
      {section === "outputs" ? (
        <>
          <div className="run-controls-panel hero-run-controls" aria-label="运行 diligence">
            <div className="hero-run-controls__primary-row">
              <div className="hero-run-controls__session-field">
                <span id="run-session-caption" className="muted hero-run-controls__caption">
                  当前 diligence session
                </span>
                <select
                  aria-labelledby="run-session-caption"
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
                    <span className={`status ${step.status}`}>{runStatusLabel(step.status)}</span>
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
        </>
      ) : null}
    </div>
  );
}
