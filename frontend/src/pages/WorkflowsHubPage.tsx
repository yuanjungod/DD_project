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
import {
  normalizeOptionalTechnicalId,
  TECHNICAL_ID_HINT,
  TECHNICAL_ID_PLACEHOLDER,
  technicalIdValidationError,
} from "../domain/technicalId";
import type { AgentTemplate, PublishedWorkflowTemplate, WorkflowGraph, WorkflowTemplate } from "../types/domain";

type HubTab = "templates" | "builder" | "agents";
type BuilderSubTab = "create" | "agents" | "saved";
const PROTECTED_WORKFLOW_TEMPLATE_IDS = new Set([
  "standard_due_diligence",
  "financial_investment_due_diligence",
  "legal_compliance_due_diligence",
  "market_entry_due_diligence",
]);

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
    id: "",
    name: "",
    description: "",
    workflow_template: "custom",
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
    setForm({ id: "", name: "", description: "", workflow_template: "custom" });
    setWorkflowGraph(createEmptyWorkflowGraph());
  }

  function beginEditWorkflow(workflow: WorkflowTemplate) {
    setEditingWorkflowId(workflow.id);
    setForm({
      id: workflow.id,
      name: workflow.name,
      description: workflow.description,
      workflow_template: workflow.workflow_template,
    });
    setWorkflowGraph(workflow.graph ?? createEmptyWorkflowGraph());
    setBuilderSubTab("create");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const graph = normalizeWorkflowGraph(workflowGraph);
      try {
        validateWorkflowGraph(graph);
      } catch (err) {
        if (err instanceof WorkflowGraphValidationError) {
          throw new Error(err.message);
        }
        throw err;
      }
      const payload = {
        name: form.name,
        description: form.description,
        workflow_template: form.workflow_template,
        graph,
      };
      if (!payload.graph.nodes.length) {
        throw new Error("请至少添加一个 Agent 节点。");
      }
      if (!editingWorkflowId) {
        const idError = technicalIdValidationError(form.id);
        if (idError) {
          throw new Error(idError);
        }
      }
      if (editingWorkflowId) {
        await updateWorkflowTemplate(editingWorkflowId, payload);
      } else {
        await createWorkflowTemplate({
          id: normalizeOptionalTechnicalId(form.id),
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
    if (PROTECTED_WORKFLOW_TEMPLATE_IDS.has(workflow.id)) {
      return;
    }
    const publishedHint =
      workflow.status === "published"
        ? "该模板已发布，删除后「模板应用」中将不再出现。确定删除吗？"
        : "确定删除该未发布模板吗？";
    if (!window.confirm(`${publishedHint}\n\n「${workflow.name}」 (${workflow.id})`)) {
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
      ? "选择已发布 Workflow Template，一键创建绑定公司的 Engagement。"
      : activeTab === "builder"
        ? "新建或编辑模板、编排 Agent、发布后与「模板应用」页同步；内置模板可修改但不可删除。"
        : "维护提示词、Skill 包、工具与资源配置，供流程模板引用。";

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Workflows</p>
        <h1>Agent 和 Workflow Templates</h1>
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
        <SectionCard title="已发布 Workflow Templates" description="可直接绑定目标公司并创建 Engagement。">
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
                    <code className="published-template-list__id">{workflowTemplate.id}</code>
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
                      ? `正在编辑 ${editingWorkflowId}；保存后更新模板内容，已发布场景需重新发布才会同步到「使用场景」。`
                      : "填写基本信息并选择执行顺序，保存后在「已保存模板」中发布。"
                  }
                >
                  {editingWorkflowId ? (
                    <div className="resource-edit-banner">
                      <span>
                        编辑模式 · <code>{editingWorkflowId}</code>
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
                        <label>
                          技术 ID（可选）
                          <input
                            value={form.id}
                            disabled={Boolean(editingWorkflowId)}
                            onChange={(event) => setForm({ ...form, id: event.target.value })}
                            placeholder={TECHNICAL_ID_PLACEHOLDER}
                          />
                          <span className="muted" style={{ fontSize: "12px" }}>
                            {TECHNICAL_ID_HINT}
                          </span>
                        </label>
                        <label>
                          名称
                          <input
                            value={form.name}
                            onChange={(event) => setForm({ ...form, name: event.target.value })}
                            required
                          />
                        </label>
                        <label>
                          模板分类
                          <input
                            value={form.workflow_template}
                            onChange={(event) => setForm({ ...form, workflow_template: event.target.value })}
                          />
                        </label>
                        <label className="workflow-template-form__span-2">
                          描述
                          <input
                            value={form.description}
                            onChange={(event) => setForm({ ...form, description: event.target.value })}
                          />
                        </label>
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
                        <strong>{agent.id}</strong>
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
                            {workflow.id} · v{workflow.version} · {workflow.graph.nodes.length} agents
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
                          {!PROTECTED_WORKFLOW_TEMPLATE_IDS.has(workflow.id) ? (
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
