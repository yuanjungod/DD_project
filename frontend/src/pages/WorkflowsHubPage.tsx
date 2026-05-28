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

function splitList(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function graphFromNodeSpecs(raw: string): WorkflowGraph {
  const lines = raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const parsed =
    lines.length === 1 && !lines[0].includes(">")
      ? splitList(lines[0]).map((master) => ({ master, subs: [] as string[] }))
      : lines.map((line) => {
          const [masterPart, subPart] = line.split(">", 2).map((s) => s.trim());
          return {
            master: masterPart,
            subs: subPart ? splitList(subPart) : [],
          };
        });

  const nodes = parsed
    .filter((row) => row.master)
    .map((row, index) => ({
    id: `node_${index + 1}`,
    agent_template_id: row.master,
    sub_agent_template_ids: row.subs,
    stage: index === 0 ? "coordination" : index === parsed.length - 1 ? "reporting" : "execution",
  }));
  return {
    nodes,
    edges: nodes.slice(0, -1).map((node, index) => ({ from: node.id, to: nodes[index + 1].id })),
    entry_node: nodes[0]?.id ?? "",
    report_node: nodes[nodes.length - 1]?.id ?? "",
  };
}

function nodeSpecsFromGraph(graph: WorkflowGraph): string {
  return (graph?.nodes ?? [])
    .map((node) => {
      const master = (node.agent_template_id ?? "").trim();
      const subs = (node.sub_agent_template_ids ?? []).map((s) => (s ?? "").trim()).filter(Boolean);
      if (!master) return "";
      return subs.length ? `${master} > ${subs.join(", ")}` : master;
    })
    .filter(Boolean)
    .join("\n");
}

type HubTab = "templates" | "builder" | "agents";

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
    scenario: "custom",
    node_specs: "",
  });
  const [editingWorkflowId, setEditingWorkflowId] = useState<string | null>(null);

  const agentPlaceholder = useMemo(() => agents.map((agent) => agent.id).join(", "), [agents]);

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
    setForm({ id: "", name: "", description: "", scenario: "custom", node_specs: "" });
  }

  function beginEditWorkflow(workflow: WorkflowTemplate) {
    setEditingWorkflowId(workflow.id);
    setForm({
      id: workflow.id,
      name: workflow.name,
      description: workflow.description,
      scenario: workflow.scenario,
      node_specs: nodeSpecsFromGraph(workflow.graph),
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const payload = {
        name: form.name,
        description: form.description,
        scenario: form.scenario,
        graph: graphFromNodeSpecs(form.node_specs),
      };
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
        : "确定删除该草稿模板吗？";
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
        ? "新建或编辑草稿、编排 Agent、发布后与「模板应用」页同步；内置模板可修改但不可删除。"
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
              <div className="grid two">
                <SectionCard
                  title={editingWorkflowId ? "编辑流程模板" : "新增流程模板"}
                  description={
                    editingWorkflowId
                      ? `正在编辑 ${editingWorkflowId}；保存后更新模板内容，已发布场景需重新发布才会同步到「使用场景」。`
                      : "逗号分隔 Agent 顺序；保存为草稿后在此页发布。"
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
                      场景分类
                      <input
                        value={form.scenario}
                        onChange={(event) => setForm({ ...form, scenario: event.target.value })}
                      />
                    </label>
                    <label>
                      节点配置（支持 master + sub）
                      <textarea
                        rows={6}
                        placeholder={`每行一个节点：\nCoordinatorAgent > CompanyProfileAgent, WebResearchAgent\nReportWriterAgent\n\n也兼容旧写法（单行逗号分隔）：\n${agentPlaceholder}`}
                        value={form.node_specs}
                        onChange={(event) => setForm({ ...form, node_specs: event.target.value })}
                      />
                    </label>
                    <label>
                      描述
                      <input
                        value={form.description}
                        onChange={(event) => setForm({ ...form, description: event.target.value })}
                      />
                    </label>
                    <button type="submit">{editingWorkflowId ? "保存修改" : "保存为草稿"}</button>
                  </form>
                </SectionCard>
                <SectionCard title="可用 Agent">
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
              </div>
              <SectionCard title="草稿与已保存模板" description="发布后即在「使用场景」中可选。">
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
