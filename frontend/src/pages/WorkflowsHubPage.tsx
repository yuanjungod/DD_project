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
import { resolveGraphAgentOrder } from "../domain/workflowGraph";
import type { AgentTemplate, PublishedWorkflowTemplate, WorkflowGraph, WorkflowTemplate } from "../types/domain";

type HubTab = "templates" | "builder" | "agents";
type BuilderSubTab = "create" | "agents" | "saved";
type OrchestrationMode = "linear" | "master_sub";
type AgentNodeForm = {
  key: string;
  master: string;
  subAgents: string[];
};

function newNodeForm(): AgentNodeForm {
  return {
    key: `tmp_${Math.random().toString(36).slice(2, 10)}`,
    master: "",
    subAgents: [],
  };
}

function graphFromNodeForms(forms: AgentNodeForm[], mode: OrchestrationMode): WorkflowGraph {
  const normalized = forms
    .map((row) => ({
      master: row.master.trim(),
      subs: mode === "master_sub" ? row.subAgents.filter(Boolean) : [],
    }))
    .filter((row) => row.master);
  const nodes = normalized.map((row, index) => ({
    id: `node_${index + 1}`,
    agent_template_id: row.master,
    sub_agent_template_ids: row.subs,
    stage: index === 0 ? "coordination" : index === normalized.length - 1 ? "reporting" : "execution",
  }));
  return {
    nodes,
    edges: nodes.slice(0, -1).map((node, index) => ({ from: node.id, to: nodes[index + 1].id })),
    entry_node: nodes[0]?.id ?? "",
    report_node: nodes[nodes.length - 1]?.id ?? "",
  };
}

function nodeFormsFromGraph(graph: WorkflowGraph): { mode: OrchestrationMode; forms: AgentNodeForm[] } {
  const rows = (graph?.nodes ?? []).map((node) => {
    const master = (node.agent_template_id ?? "").trim();
    const subAgents = (node.sub_agent_template_ids ?? []).map((item) => (item ?? "").trim()).filter(Boolean);
    return {
      key: node.id || `tmp_${Math.random().toString(36).slice(2, 10)}`,
      master,
      subAgents,
    } as AgentNodeForm;
  });
  const mode: OrchestrationMode = rows.some((row) => row.subAgents.length) ? "master_sub" : "linear";
  return { mode, forms: rows.length ? rows : [newNodeForm()] };
}

/** Must match backend `workflow_template_files._PROTECTED_WORKFLOW_TEMPLATE_IDS`. */
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
  const [nodeForms, setNodeForms] = useState<AgentNodeForm[]>([newNodeForm()]);
  const [orchestrationMode, setOrchestrationMode] = useState<OrchestrationMode>("linear");
  const [editingWorkflowId, setEditingWorkflowId] = useState<string | null>(null);
  const [builderSubTab, setBuilderSubTab] = useState<BuilderSubTab>("create");

  const agentById = useMemo(() => new Map(agents.map((agent) => [agent.id, agent])), [agents]);
  const selectableAgents = useMemo(() => agents.filter((agent) => agent.enabled), [agents]);
  const allowMasterSubMode = Boolean(editingWorkflowId);

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
    setNodeForms([newNodeForm()]);
    setOrchestrationMode("linear");
  }

  function beginEditWorkflow(workflow: WorkflowTemplate) {
    setEditingWorkflowId(workflow.id);
    setForm({
      id: workflow.id,
      name: workflow.name,
      description: workflow.description,
      workflow_template: workflow.workflow_template,
    });
    const nodeConfig = nodeFormsFromGraph(workflow.graph);
    setOrchestrationMode(nodeConfig.mode);
    setNodeForms(nodeConfig.forms);
    setBuilderSubTab("create");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function addNodeForm() {
    setNodeForms((prev) => [...prev, newNodeForm()]);
  }

  function removeNodeForm(key: string) {
    setNodeForms((prev) => {
      const next = prev.filter((item) => item.key !== key);
      return next.length ? next : [newNodeForm()];
    });
  }

  function updateNodeForm(key: string, patch: Partial<AgentNodeForm>) {
    setNodeForms((prev) =>
      prev.map((item) => {
        if (item.key !== key) return item;
        const next: AgentNodeForm = { ...item, ...patch };
        next.subAgents = next.subAgents.filter((id) => id !== next.master);
        return next;
      }),
    );
  }

  function toggleSubAgentForNode(key: string, agentId: string) {
    if (orchestrationMode !== "master_sub") return;
    setNodeForms((prev) =>
      prev.map((item) => {
        if (item.key !== key) return item;
        const has = item.subAgents.includes(agentId);
        return {
          ...item,
          subAgents: has ? item.subAgents.filter((id) => id !== agentId) : [...item.subAgents, agentId],
        };
      }),
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const payload = {
        name: form.name,
        description: form.description,
        workflow_template: form.workflow_template,
        graph: graphFromNodeForms(nodeForms, allowMasterSubMode ? orchestrationMode : "linear"),
      };
      if (!payload.graph.nodes.length) {
        throw new Error("请至少配置一个步骤并选择 Agent。");
      }
      if (editingWorkflowId) {
        await updateWorkflowTemplate(editingWorkflowId, payload);
      } else {
        await createWorkflowTemplate({
          id: form.id || undefined,
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
          <div className="workflow-template-grid">
            {publishedWorkflowTemplates.map((workflowTemplate) => (
              <SectionCard key={workflowTemplate.id} title={workflowTemplate.name} description={workflowTemplate.description}>
                <div className="tag-row">
                  <span>{workflowTemplate.workflow_template}</span>
                  <span>{workflowTemplate.agents.length} agents</span>
                </div>
                <ol className="agent-chain">
                  {workflowTemplate.agents.map((agent) => (
                    <li key={`${workflowTemplate.id}-${agent}`}>{agent}</li>
                  ))}
                </ol>
                <Link className="button-link" to={`/engagements/new?workflow=${workflowTemplate.id}`}>
                  应用到 Engagement
                </Link>
              </SectionCard>
            ))}
          </div>
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
                    <div className="form-section workflow-template-form__meta">
                      <h3 className="form-section__title">基本信息</h3>
                      <div className="workflow-template-form__meta-grid">
                        <label>
                          ID
                          <input
                            value={form.id}
                            disabled={Boolean(editingWorkflowId)}
                            onChange={(event) => setForm({ ...form, id: event.target.value })}
                            placeholder="留空则自动生成"
                          />
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

                    {allowMasterSubMode ? (
                      <label className="workflow-template-form__mode">
                        编排模式
                        <select
                          value={orchestrationMode}
                          onChange={(event) => setOrchestrationMode(event.target.value as OrchestrationMode)}
                        >
                          <option value="linear">串行</option>
                          <option value="master_sub">主从（仅编辑旧模板）</option>
                        </select>
                      </label>
                    ) : null}

                    <div className="form-section workflow-pipeline">
                      <div className="workflow-pipeline__header">
                        <div>
                          <h3 className="form-section__title">执行顺序</h3>
                          <p className="muted">按步骤依次执行，点击卡片选择 Agent。</p>
                        </div>
                        <button type="button" className="secondary-button workflow-pipeline__add-step" onClick={addNodeForm}>
                          添加步骤
                        </button>
                      </div>

                      {selectableAgents.length === 0 ? (
                        <p className="workflow-pipeline__empty">暂无可用 Agent，请先在「Agent 配置」中创建并启用。</p>
                      ) : (
                        <ol className="workflow-pipeline__list">
                          {nodeForms.map((node, index) => {
                            const selected = node.master ? agentById.get(node.master) : undefined;
                            const missingSelected = node.master && !selected;
                            const collaboratorIds = [
                              ...selectableAgents
                                .filter((agent) => agent.id !== node.master)
                                .map((agent) => agent.id),
                              ...node.subAgents.filter(
                                (agentId) =>
                                  agentId !== node.master && !selectableAgents.some((agent) => agent.id === agentId),
                              ),
                            ];
                            return (
                              <li key={node.key} className="workflow-pipeline__item">
                                {index > 0 ? <div className="workflow-pipeline__connector" aria-hidden="true" /> : null}
                                <article className="workflow-pipeline__step">
                                  <div className="workflow-pipeline__step-head">
                                    <span className="workflow-pipeline__step-badge">{index + 1}</span>
                                    <div className="workflow-pipeline__step-title">
                                      <strong>步骤 {index + 1}</strong>
                                      {selected ? (
                                        <span className="workflow-pipeline__step-sub">{selected.role}</span>
                                      ) : missingSelected ? (
                                        <span className="workflow-pipeline__step-sub muted">{node.master}</span>
                                      ) : (
                                        <span className="workflow-pipeline__step-sub muted">未选择</span>
                                      )}
                                    </div>
                                    {nodeForms.length > 1 ? (
                                      <button
                                        type="button"
                                        className="workflow-pipeline__remove"
                                        onClick={() => removeNodeForm(node.key)}
                                      >
                                        移除
                                      </button>
                                    ) : null}
                                  </div>

                                  <div className="workflow-pipeline__agent-grid" role="listbox" aria-label={`步骤 ${index + 1} Agent`}>
                                    {selectableAgents.map((agent) => (
                                      <button
                                        key={`${node.key}-${agent.id}`}
                                        type="button"
                                        role="option"
                                        aria-selected={node.master === agent.id}
                                        className={`workflow-agent-chip ${node.master === agent.id ? "is-selected" : ""}`}
                                        onClick={() => updateNodeForm(node.key, { master: agent.id })}
                                      >
                                        <span className="workflow-agent-chip__name">{agent.name || agent.id}</span>
                                        <code>{agent.id}</code>
                                      </button>
                                    ))}
                                    {missingSelected ? (
                                      <button
                                        type="button"
                                        className="workflow-agent-chip is-selected is-missing"
                                        onClick={() => updateNodeForm(node.key, { master: node.master })}
                                      >
                                        <span className="workflow-agent-chip__name">{node.master}</span>
                                        <code>不在当前目录</code>
                                      </button>
                                    ) : null}
                                  </div>

                                  {allowMasterSubMode && orchestrationMode === "master_sub" && node.master ? (
                                    <div className="workflow-pipeline__collab">
                                      <p className="workflow-pipeline__collab-label">协作（可选，多选）</p>
                                      <div className="workflow-pipeline__agent-grid workflow-pipeline__agent-grid--compact">
                                        {collaboratorIds.map((agentId) => {
                                          const agent = agentById.get(agentId);
                                          const checked = node.subAgents.includes(agentId);
                                          return (
                                            <button
                                              key={`${node.key}-collab-${agentId}`}
                                              type="button"
                                              className={`workflow-agent-chip workflow-agent-chip--collab ${checked ? "is-selected" : ""}`}
                                              onClick={() => toggleSubAgentForNode(node.key, agentId)}
                                            >
                                              <span className="workflow-agent-chip__name">
                                                {agent?.name || agentId}
                                              </span>
                                              <code>{agentId}</code>
                                            </button>
                                          );
                                        })}
                                      </div>
                                    </div>
                                  ) : null}
                                </article>
                              </li>
                            );
                          })}
                        </ol>
                      )}
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
                          {resolveGraphAgentOrder(workflow.graph).map((agentId, index) => (
                            <li key={`${workflow.id}-${agentId}-${index}`}>{agentId}</li>
                          ))}
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
