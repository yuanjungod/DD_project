import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  cloneWorkflowTemplate,
  createWorkflowTemplate,
  deleteWorkflowTemplate,
  listAgentTemplates,
  listPublishedWorkflowTemplates,
  listWorkflowTemplates,
  publishWorkflowTemplate,
  updateWorkflowTemplate,
} from "../api/client";
import { AgentTemplatesPanel } from "../components/AgentTemplatesPanel";
import { SectionCard } from "../components/SectionCard";
import { WorkflowGraphEditor } from "../components/WorkflowGraphEditor";
import {
  createEmptyWorkflowGraph,
  normalizeWorkflowGraph,
  resolveGraphAgentOrder,
  validateWorkflowGraph,
  WorkflowGraphValidationError,
} from "../domain/workflowGraph";
import { catalogDisplayName, duplicateCatalogNameError, findDuplicateCatalogName } from "../domain/catalogNames";
import type { AgentTemplate, PublishedWorkflowTemplate, WorkflowGraph, WorkflowTemplate } from "../types/domain";

type HubTab = "templates" | "builder" | "agents";
type BuilderSubTab = "create" | "agents" | "saved";
const DEFAULT_DOCKER_IDLE_TTL_MINUTES = 20;
const MIN_DOCKER_IDLE_TTL_MINUTES = 1;
const MAX_DOCKER_IDLE_TTL_MINUTES = 24 * 60;

export function WorkflowsHubPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const activeTab: HubTab =
    tabParam === "builder" ? "builder" : tabParam === "agents" ? "agents" : "templates";

  const [error, setError] = useState("");

  const setActiveTab = useCallback(
    (next: HubTab) => {
      setError("");
      const nextParams = new URLSearchParams(searchParams);
      if (next === "templates") {
        nextParams.delete("tab");
      } else {
        nextParams.set("tab", next);
      }
      setSearchParams(nextParams, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const [publishedWorkflowTemplates, setPublishedWorkflowTemplates] = useState<PublishedWorkflowTemplate[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowTemplate[]>([]);
  const [agents, setAgents] = useState<AgentTemplate[]>([]);
  const [builderLoaded, setBuilderLoaded] = useState(false);
  const [form, setForm] = useState({
    name: "",
    description: "",
    workflow_template: "custom",
    command_execution: "host" as "host" | "docker",
    idle_ttl_minutes: DEFAULT_DOCKER_IDLE_TTL_MINUTES,
  });
  const [workflowGraph, setWorkflowGraph] = useState<WorkflowGraph>(createEmptyWorkflowGraph());
  const [editingWorkflowId, setEditingWorkflowId] = useState<string | null>(null);
  const [builderSubTab, setBuilderSubTab] = useState<BuilderSubTab>("create");

  const agentById = useMemo(() => new Map(agents.map((agent) => [agent.id, agent])), [agents]);

  const loadPublishedWorkflowTemplates = useCallback(async () => {
    const items = await listPublishedWorkflowTemplates();
    setPublishedWorkflowTemplates(items);
  }, []);

  const loadBuilder = useCallback(async () => {
    const [workflowItems, agentItems] = await Promise.all([listWorkflowTemplates(), listAgentTemplates()]);
    setWorkflows(workflowItems);
    setAgents(agentItems);
    setBuilderLoaded(true);
  }, []);

  useEffect(() => {
    loadPublishedWorkflowTemplates().catch((err: unknown) => setError(String(err)));
  }, [loadPublishedWorkflowTemplates]);

  useEffect(() => {
    if (activeTab !== "builder" || builderLoaded) {
      return;
    }
    loadBuilder().catch((err: unknown) => setError(String(err)));
  }, [activeTab, builderLoaded, loadBuilder]);

  async function refreshAfterMutation() {
    await loadPublishedWorkflowTemplates();
    if (builderLoaded || activeTab === "builder") {
      await loadBuilder();
    }
  }

  function resetWorkflowForm() {
    setEditingWorkflowId(null);
    setForm({
      name: "",
      description: "",
      workflow_template: "custom",
      command_execution: "host",
      idle_ttl_minutes: DEFAULT_DOCKER_IDLE_TTL_MINUTES,
    });
    setWorkflowGraph(createEmptyWorkflowGraph());
  }

  function beginEditWorkflow(workflow: WorkflowTemplate) {
    setEditingWorkflowId(workflow.id);
    setForm({
      name: workflow.name,
      description: workflow.description,
      workflow_template: workflow.workflow_template,
      command_execution: workflow.runtime?.command_execution === "docker" ? "docker" : "host",
      idle_ttl_minutes: Math.round(
        (workflow.runtime?.docker?.idle_ttl_seconds ?? DEFAULT_DOCKER_IDLE_TTL_MINUTES * 60) / 60,
      ),
    });
    setWorkflowGraph(workflow.graph ?? createEmptyWorkflowGraph());
    setBuilderSubTab("create");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const editingWorkflow = editingWorkflowId ? workflows.find((workflow) => workflow.id === editingWorkflowId) : undefined;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const nameError = duplicateCatalogNameError(
        "流程模板",
        form.name,
        findDuplicateCatalogName(workflows, form.name, editingWorkflowId),
      );
      if (nameError) {
        throw new Error(nameError);
      }
      const graph = normalizeWorkflowGraph(workflowGraph);
      try {
        validateWorkflowGraph(graph);
      } catch (err) {
        if (err instanceof WorkflowGraphValidationError) {
          throw new Error(err.message);
        }
        throw err;
      }
      const idleMinutes = Math.min(
        MAX_DOCKER_IDLE_TTL_MINUTES,
        Math.max(MIN_DOCKER_IDLE_TTL_MINUTES, Math.round(form.idle_ttl_minutes) || DEFAULT_DOCKER_IDLE_TTL_MINUTES),
      );
      const payload = {
        name: form.name,
        description: form.description,
        workflow_template: form.workflow_template,
        graph,
        runtime: {
          command_execution: form.command_execution,
          docker: {
            image: "harness-exec:0.1.0",
            idle_ttl_seconds: idleMinutes * 60,
            workspace_mount: "workflow_tree",
          },
        },
      };
      if (!payload.graph.nodes.length) {
        throw new Error("请至少添加一个 Agent 节点。");
      }
      if (editingWorkflowId) {
        await updateWorkflowTemplate(editingWorkflowId, payload);
      } else {
        await createWorkflowTemplate({
          ...payload,
          status: "draft",
          version: 1,
        });
      }
      resetWorkflowForm();
      await refreshAfterMutation();
    } catch (err) {
      setError(String(err));
    }
  }

  async function handlePublish(workflowId: string) {
    setError("");
    try {
      await publishWorkflowTemplate(workflowId);
      await refreshAfterMutation();
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleClone(workflowId: string) {
    setError("");
    try {
      await cloneWorkflowTemplate(workflowId);
      await refreshAfterMutation();
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleDelete(workflow: WorkflowTemplate) {
    if (workflow.is_builtin) {
      return;
    }
    const publishedHint =
      workflow.status === "published"
        ? "该模板已发布，删除后「模板应用」中将不再出现。确定删除吗？"
        : "确定删除该未发布模板吗？";
    if (!window.confirm(`${publishedHint}\n\n「${workflow.name}」`)) {
      return;
    }
    setError("");
    try {
      await deleteWorkflowTemplate(workflow.id);
      await refreshAfterMutation();
    } catch (err) {
      setError(String(err));
    }
  }

  const heroDescription =
    activeTab === "templates"
      ? "选择已发布 Workflow Template，创建任务并填写需要完成的工作内容。"
      : activeTab === "builder"
        ? "新建或编辑模板、编排 Agent、发布后与「模板应用」页同步；内置模板可修改但不可删除。"
        : "维护提示词、Skill 包与资源配置，供流程模板引用。";

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Workflows</p>
        <h1>Harness · Agent 与工作流</h1>
        <p>{heroDescription}</p>
        <nav className="hub-tab-bar" aria-label="工作流分区">
          <button
            type="button"
            className="hub-tab"
            aria-current={activeTab === "templates" ? "page" : undefined}
            onClick={() => setActiveTab("templates")}
          >
            模板应用
          </button>
          <button
            type="button"
            className="hub-tab"
            aria-current={activeTab === "builder" ? "page" : undefined}
            onClick={() => setActiveTab("builder")}
          >
            模板管理
          </button>
          <button
            type="button"
            className="hub-tab"
            aria-current={activeTab === "agents" ? "page" : undefined}
            onClick={() => setActiveTab("agents")}
          >
            Agent 配置
          </button>
        </nav>
      </header>
      {error ? <div className="error">{error}</div> : null}

      {activeTab === "templates" ? (
        <SectionCard title="已发布 Workflow Templates" description="选择模板创建任务，并在下一步用自然语言描述本次要完成的具体工作。">
          {publishedWorkflowTemplates.length === 0 ? (
            <p className="muted">暂无已发布模板，请先在「模板管理」中创建并发布。</p>
          ) : (
            <div className="published-template-list" aria-label="已发布模板列表">
              <div className="published-template-list__row published-template-list__row--head">
                <span className="published-template-list__cell published-template-list__cell--head">模板</span>
                <span className="published-template-list__cell published-template-list__cell--head">Agent 链</span>
                <span className="published-template-list__cell published-template-list__cell--head published-template-list__cell--center">
                  类型
                </span>
                <span className="published-template-list__cell published-template-list__cell--head published-template-list__cell--center">
                  操作
                </span>
              </div>
              {publishedWorkflowTemplates.map((workflowTemplate) => (
                <article key={workflowTemplate.id} className="published-template-list__row">
                  <div className="published-template-list__cell published-template-list__name">
                    <strong>{workflowTemplate.name}</strong>
                    {workflowTemplate.description ? (
                      <p className="published-template-list__desc">{workflowTemplate.description}</p>
                    ) : null}
                  </div>
                  <p className="published-template-list__cell published-template-list__agents" title={workflowTemplate.agents.join(" → ")}>
                    {workflowTemplate.agents.join(" → ")}
                  </p>
                  <span className="published-template-list__cell published-template-list__type">{workflowTemplate.workflow_template}</span>
                  <div className="published-template-list__cell published-template-list__action-cell">
                    <Link className="button-link published-template-list__action" to={`/engagements/new?workflow=${workflowTemplate.id}`}>
                      应用
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          )}
        </SectionCard>
      ) : activeTab === "builder" ? (
        <>
          {!builderLoaded ? <p className="notice">加载流程与 Agent 目录…</p> : null}
          {builderLoaded ? (
            <>
              <nav className="hub-tab-bar" aria-label="模板管理子页面">
                <button
                  type="button"
                  className="hub-tab"
                  aria-current={builderSubTab === "create" ? "page" : undefined}
                  onClick={() => setBuilderSubTab("create")}
                >
                  新增流程模板
                </button>
                <button
                  type="button"
                  className="hub-tab"
                  aria-current={builderSubTab === "agents" ? "page" : undefined}
                  onClick={() => setBuilderSubTab("agents")}
                >
                  可用Agent
                </button>
                <button
                  type="button"
                  className="hub-tab"
                  aria-current={builderSubTab === "saved" ? "page" : undefined}
                  onClick={() => setBuilderSubTab("saved")}
                >
                  已保存模板
                </button>
              </nav>

              {builderSubTab === "create" ? (
                <SectionCard
                  title={editingWorkflowId ? "编辑流程模板" : "新增流程模板"}
                  description={
                    editingWorkflowId
                      ? `正在编辑「${editingWorkflow?.name ?? "流程模板"}」；保存后更新模板内容，已发布场景需重新发布才会同步到「使用场景」。`
                      : "填写基本信息并选择执行顺序，保存后在「已保存模板」中发布。"
                  }
                >
                  {editingWorkflowId ? (
                    <div className="resource-edit-banner">
                      <span>
                        编辑模式 · {editingWorkflow?.name ?? "流程模板"}
                      </span>
                      <button type="button" className="secondary-button" onClick={() => resetWorkflowForm()}>
                        取消编辑
                      </button>
                    </div>
                  ) : null}
                  <form className="form workflow-template-form" onSubmit={handleSubmit}>
                    <div className="form-section workflow-graph-section">
                      <div className="workflow-graph-section__header">
                        <div>
                          <h3 className="form-section__title">流程编排</h3>
                          <p className="muted">
                            连线带箭头：箭尾为被依赖 Agent，箭头指向依赖方；无依赖节点同层并行。选中连线后按 Delete 可删除，或双击连线直接删除。
                          </p>
                        </div>
                      </div>
                      <WorkflowGraphEditor graph={workflowGraph} agents={agents} onChange={setWorkflowGraph} />
                    </div>

                    <div className="form-section workflow-template-form__meta">
                      <h3 className="form-section__title">基本信息</h3>
                      <div className="workflow-template-form__meta-grid">
                        <label className="workflow-field">
                          <span className="workflow-field__label">名称</span>
                          <input
                            value={form.name}
                            onChange={(event) => setForm({ ...form, name: event.target.value })}
                            placeholder="在界面中展示的名称"
                            required
                          />
                        </label>
                        <label className="workflow-field">
                          <span className="workflow-field__label">模板分类</span>
                          <input
                            value={form.workflow_template}
                            onChange={(event) => setForm({ ...form, workflow_template: event.target.value })}
                            placeholder="custom"
                          />
                          <span className="workflow-field__hint">用于区分模板族，如 custom、standard</span>
                        </label>
                        <label className="workflow-field">
                          <span className="workflow-field__label">描述</span>
                          <input
                            value={form.description}
                            onChange={(event) => setForm({ ...form, description: event.target.value })}
                            placeholder="简要说明该模板的用途"
                          />
                        </label>
                        <div className="workflow-template-form__span-2 workflow-runtime-panel">
                          <div className="workflow-runtime-panel__head">
                            <span className="workflow-field__label">命令执行环境</span>
                            <span className="workflow-runtime-panel__badge">Agent 工具链</span>
                          </div>
                          <div className="workflow-runtime-picker" role="radiogroup" aria-label="命令执行环境">
                            <button
                              type="button"
                              role="radio"
                              aria-checked={form.command_execution === "host"}
                              className={
                                form.command_execution === "host"
                                  ? "workflow-runtime-picker__option workflow-runtime-picker__option--active"
                                  : "workflow-runtime-picker__option"
                              }
                              onClick={() => setForm({ ...form, command_execution: "host" })}
                            >
                              <span className="workflow-runtime-picker__title">Host · 本机</span>
                              <span className="workflow-runtime-picker__desc">
                                Shell / Python / 读写在 agent_service 进程内执行
                              </span>
                            </button>
                            <button
                              type="button"
                              role="radio"
                              aria-checked={form.command_execution === "docker"}
                              className={
                                form.command_execution === "docker"
                                  ? "workflow-runtime-picker__option workflow-runtime-picker__option--active workflow-runtime-picker__option--docker"
                                  : "workflow-runtime-picker__option"
                              }
                              onClick={() => setForm({ ...form, command_execution: "docker" })}
                            >
                              <span className="workflow-runtime-picker__title">Docker · 隔离容器</span>
                              <span className="workflow-runtime-picker__desc">
                                每用户 × 模板独立容器；LLM 仍在主机
                              </span>
                            </button>
                          </div>
                          {form.command_execution === "docker" ? (
                            <label className="workflow-field workflow-field--inline">
                              <span className="workflow-field__label">空闲自动停止（分钟）</span>
                              <input
                                type="number"
                                min={MIN_DOCKER_IDLE_TTL_MINUTES}
                                max={MAX_DOCKER_IDLE_TTL_MINUTES}
                                step={1}
                                value={form.idle_ttl_minutes}
                                onChange={(event) =>
                                  setForm({
                                    ...form,
                                    idle_ttl_minutes: Number(event.target.value) || DEFAULT_DOCKER_IDLE_TTL_MINUTES,
                                  })
                                }
                              />
                              <span className="workflow-field__hint">
                                无 Shell/Python/读文件活动超过该时间后，agent_service 将停止对应执行容器（至少 1 分钟）。
                              </span>
                            </label>
                          ) : null}
                          <p className="workflow-field__hint">
                            Docker 模式需预先构建镜像{" "}
                            <code className="workflow-inline-code">harness-exec:0.1.0</code>
                            ，挂载该用户工作流目录；命令与文件读写均在容器内完成。
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="workflow-template-form__actions">
                      <button type="submit">{editingWorkflowId ? "保存修改" : "保存"}</button>
                    </div>
                  </form>
                </SectionCard>
              ) : null}

              {builderSubTab === "agents" ? (
                <SectionCard title="可用 Agent" description="流程模板可引用的 Agent 列表。">
                  <ul className="list">
                    {agents.map((agent) => (
                      <li key={agent.id}>
                        <span>{agent.enabled ? "enabled" : "disabled"}</span>
                        <strong>{catalogDisplayName(agent)}</strong>
                        <p>{agent.role}</p>
                      </li>
                    ))}
                  </ul>
                </SectionCard>
              ) : null}

              {builderSubTab === "saved" ? (
                <SectionCard title="已保存模板" description="发布后即在「使用场景」中可选。">
                  <div className="workflow-list">
                    {workflows.map((workflow) => (
                      <article key={workflow.id} className="workflow-row">
                        <div>
                          <span className={`status ${workflow.status}`}>{workflow.status}</span>
                          <h3>{workflow.name}</h3>
                          <p>{workflow.description}</p>
                          <small>
                            v{workflow.version} · {workflow.graph.nodes.length} 个 Agent
                          </small>
                        </div>
                        <ol className="agent-chain">
                          {resolveGraphAgentOrder(workflow.graph).map((agentId, index) => {
                            const agent = agentById.get(agentId);
                            return (
                              <li key={`${workflow.id}-${agentId}-${index}`}>{agent?.name || agentId}</li>
                            );
                          })}
                        </ol>
                        <div className="row-actions">
                          <button type="button" className="secondary-button" onClick={() => beginEditWorkflow(workflow)}>
                            编辑
                          </button>
                          <button type="button" onClick={() => handlePublish(workflow.id)}>
                            发布
                          </button>
                          <button type="button" className="secondary-button" onClick={() => handleClone(workflow.id)}>
                            克隆
                          </button>
                          {!workflow.is_builtin ? (
                            <button
                              type="button"
                              className="danger-button"
                              onClick={() => void handleDelete(workflow)}
                            >
                              删除
                            </button>
                          ) : null}
                        </div>
                      </article>
                    ))}
                  </div>
                </SectionCard>
              ) : null}
            </>
          ) : null}
        </>
      ) : (
        <AgentTemplatesPanel
          onAgentsChanged={() => {
            if (builderLoaded) {
              void loadBuilder().catch((err: unknown) => setError(String(err)));
            }
          }}
        />
      )}
    </div>
  );
}
