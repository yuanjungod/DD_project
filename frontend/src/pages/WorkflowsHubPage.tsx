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

  const availableAgentIds = useMemo(() => agents.map((agent) => agent.id), [agents]);
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
        throw new Error("请至少配置一个节点并选择主Agent。");
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
                      : "逗号分隔 Agent 顺序；先保存，再在「已保存模板」里发布。"
                  }
                >
                  {editingWorkflowId ? (
                    <div className="resource-edit-banner">
                      <span>
                        编辑模式 · <code>{editingWorkflowId}</code>
                      </span>
                      <button type="button" className="ghost-button" onClick={() => resetWorkflowForm()}>
                        取消编辑
                      </button>
                    </div>
                  ) : null}
                  <form className="form" onSubmit={handleSubmit}>
                    <label>
                      ID
                      <input
                        value={form.id}
                        disabled={Boolean(editingWorkflowId)}
                        onChange={(event) => setForm({ ...form, id: event.target.value })}
                      />
                    </label>
                    <label>
                      名称
                      <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
                    </label>
                    <label>
                      模板分类
                      <input
                        value={form.workflow_template}
                        onChange={(event) => setForm({ ...form, workflow_template: event.target.value })}
                      />
                    </label>
                    <label>
                      编排模式
                      <select
                        value={orchestrationMode}
                        onChange={(event) => {
                          const next = event.target.value as OrchestrationMode;
                          if (!allowMasterSubMode && next === "master_sub") return;
                          setOrchestrationMode(next);
                        }}
                      >
                        <option value="linear">串行编排（单Agent节点）</option>
                        {allowMasterSubMode ? <option value="master_sub">主从编排（主Agent + 从Agent）</option> : null}
                      </select>
                      {!allowMasterSubMode ? (
                        <small className="muted">新增流程模板暂不支持主从编排。</small>
                      ) : null}
                    </label>
                    <label>
                      节点配置
                      <div className="workflow-node-editor">
                        {nodeForms.map((node, index) => (
                          <div key={node.key} className="workflow-node-editor__row">
                            <div className="workflow-node-editor__row-head">
                              <strong>节点 {index + 1}</strong>
                              <button type="button" className="secondary-button" onClick={() => removeNodeForm(node.key)}>
                                删除节点
                              </button>
                            </div>
                            <label>
                              主Agent
                              <select
                                value={node.master}
                                onChange={(event) => updateNodeForm(node.key, { master: event.target.value })}
                              >
                                <option value="">请选择</option>
                                {availableAgentIds.map((agentId) => (
                                  <option key={`${node.key}-${agentId}`} value={agentId}>
                                    {agentId}
                                  </option>
                                ))}
                                {node.master && !availableAgentIds.includes(node.master) ? (
                                  <option value={node.master}>{node.master}</option>
                                ) : null}
                              </select>
                            </label>
                            {allowMasterSubMode && orchestrationMode === "master_sub" ? (
                              <fieldset>
                                <legend>从Agent（可多选）</legend>
                                <div className="checkbox-group">
                                  {availableAgentIds
                                    .filter((agentId) => agentId !== node.master)
                                    .map((agentId) => (
                                      <label key={`${node.key}-sub-${agentId}`}>
                                        <input
                                          type="checkbox"
                                          checked={node.subAgents.includes(agentId)}
                                          onChange={() => toggleSubAgentForNode(node.key, agentId)}
                                        />
                                        {agentId}
                                      </label>
                                    ))}
                                  {node.subAgents
                                    .filter((agentId) => !availableAgentIds.includes(agentId))
                                    .map((agentId) => (
                                      <label key={`${node.key}-sub-missing-${agentId}`}>
                                        <input
                                          type="checkbox"
                                          checked
                                          onChange={() => toggleSubAgentForNode(node.key, agentId)}
                                        />
                                        {agentId}
                                      </label>
                                    ))}
                                </div>
                              </fieldset>
                            ) : null}
                          </div>
                        ))}
                        <button type="button" className="secondary-button" onClick={addNodeForm}>
                          + 新增节点
                        </button>
                      </div>
                    </label>
                    <label>
                      描述
                      <input
                        value={form.description}
                        onChange={(event) => setForm({ ...form, description: event.target.value })}
                      />
                    </label>
                    <button type="submit">{editingWorkflowId ? "保存修改" : "保存"}</button>
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
