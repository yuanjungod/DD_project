import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import {
  continueStepGated,
  getRun,
  listDiligenceSessions,
  listEvidence,
  listProjectRuns,
  listProjects,
  listReports,
  listResources,
  listStepReviewChatTurns,
  postStepReviewChat,
  startRun,
} from "../api/client";
import { ProjectResourcesPanel } from "../components/ProjectResourcesPanel";
import { SectionCard } from "../components/SectionCard";
import { workflowName } from "../data/workflows";
import type {
  AgentRun,
  DiligenceSessionModel,
  Evidence,
  Project,
  Report,
  Resource,
  StepReviewChatTurn,
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

export function ProjectDetailPage() {
  const { projectId = "" } = useParams();
  const [project, setProject] = useState<Project | null>(null);
  const [resources, setResources] = useState<Resource[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
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
  const [pollingRunId, setPollingRunId] = useState<string | null>(null);

  async function refresh() {
    const [projects, resourceItems, evidenceItems, reportItems, runItems, sessionItems] = await Promise.all([
      listProjects(),
      listResources(projectId),
      listEvidence(projectId),
      listReports(projectId),
      listProjectRuns(projectId),
      listDiligenceSessions(projectId),
    ]);
    setProject(projects.find((item) => item.id === projectId) ?? null);
    setResources(resourceItems);
    setEvidence(evidenceItems);
    setReports(reportItems);
    setRuns(runItems);
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
        const [runItems, evidenceItems] = await Promise.all([listProjectRuns(projectId), listEvidence(projectId)]);
        setRuns(runItems);
        setEvidence(evidenceItems);
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

  return (
    <div className="page-stack">
      <header className="page-hero action-hero action-hero--align-start">
        <div>
          <p className="eyebrow">Application Detail</p>
          <h1>{project?.company_config.target_company.name ?? "尽调应用"}</h1>
          <p>
            {project
              ? `${workflowName(project.company_config.scope.workflow_template_id ?? project.company_config.scope.workflow_id)} · v${
                  project.company_config.scope.workflow_template_version ?? 1
                }`
              : "加载中"}
          </p>
        </div>
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
      </header>
      {error ? <div className="error">{error}</div> : null}
      <div className="grid two">
        <SectionCard
          title="应用资源"
          description="按类型配置：可信/屏蔽来源、竞品、文件引用、非结构化线索与指标定义。启动 Run 时会并入 company_config 供 Agent 使用。"
        >
          <ProjectResourcesPanel projectId={projectId} resources={resources} onRefresh={() => refresh()} />
        </SectionCard>
        <SectionCard title="本应用历史 Run">
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
      </div>
      {pausedReviewStep && activeRun?.id ? (
        <SectionCard
          title="本步复核对话"
          description={`与 ${pausedReviewStep.agent} 对齐输出、纠错或补充（步骤 ${pausedReviewStep.id}）`}
        >
          <div className="review-chat-turns">
            {(reviewChatByStep[pausedReviewStep.id] ?? []).map((t) => (
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
              placeholder="校验意见、纠错或追问…"
              value={reviewChatDraft}
              onChange={(e) => setReviewChatDraft(e.target.value)}
              disabled={reviewChatSending}
            />
            <button
              type="button"
              onClick={() => void handleSendReviewChat()}
              disabled={reviewChatSending || !reviewChatDraft.trim()}
            >
              {reviewChatSending ? "发送中…" : "发送至 Agent"}
            </button>
            <button
              type="button"
              onClick={() => void handleContinueStepGated()}
              disabled={continueLoading}
            >
              {continueLoading ? "继续执行中…" : "校验完成，继续下一步"}
            </button>
          </div>
        </SectionCard>
      ) : null}
      <div className="grid three">
        <SectionCard title="Agent 执行状态">
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
              流程进行中；步骤与证据会随回调或轮询持续刷新。
            </p>
          ) : null}
        </SectionCard>
        <SectionCard title="证据库">
          {runInFlight && evidence.length === 0 ? (
            <p className="muted">证据会随各 Agent 回调写入；若未配置回调，将在 Run 结束后一次性展示。</p>
          ) : null}
          <ul className="list evidence-list">
            {evidence.map((item) => (
              <li key={item.id}>
                <span>{item.collected_by}</span>
                <strong>{item.title}</strong>
                <p>{item.excerpt}</p>
              </li>
            ))}
          </ul>
        </SectionCard>
        <SectionCard title="尽调报告">
          {runInFlight && !reports[0] ? (
            <p className="muted">报告在 Run 成功完成后写入；请稍候或留意上方 Run 状态。</p>
          ) : null}
          {reports[0] ? (
            <article className="report">
              <h3>{reports[0].title}</h3>
              <span className={`risk ${reports[0].overall_risk}`}>整体风险：{reports[0].overall_risk}</span>
              <p>{reports[0].executive_summary}</p>
            </article>
          ) : !runInFlight ? (
            <p className="muted">完成 run 后生成报告。</p>
          ) : null}
        </SectionCard>
      </div>
    </div>
  );
}
