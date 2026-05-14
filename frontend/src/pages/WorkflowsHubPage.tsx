import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  cloneWorkflowTemplate,
  createWorkflowTemplate,
  deleteWorkflowTemplate,
  listAgentTemplates,
  listScenarios,
  listWorkflowTemplates,
  publishWorkflowTemplate,
} from "../api/client";
import { AgentTemplatesPanel } from "../components/AgentTemplatesPanel";
import { SectionCard } from "../components/SectionCard";
import type { AgentTemplate, Scenario, WorkflowGraph, WorkflowTemplate } from "../types/domain";

function splitList(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function graphFromAgents(agentIds: string[]): WorkflowGraph {
  const nodes = agentIds.map((agentId, index) => ({
    id: `node_${index + 1}`,
    agent_template_id: agentId,
    stage: index === 0 ? "coordination" : index === agentIds.length - 1 ? "reporting" : "execution",
  }));
  return {
    nodes,
    edges: nodes.slice(0, -1).map((node, index) => ({ from: node.id, to: nodes[index + 1].id })),
    entry_node: nodes[0]?.id ?? "",
    report_node: nodes[nodes.length - 1]?.id ?? "",
  };
}

type HubTab = "scenarios" | "builder" | "agents";

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
    tabParam === "builder" ? "builder" : tabParam === "agents" ? "agents" : "scenarios";

  const [error, setError] = useState("");

  const setActiveTab = useCallback(
    (next: HubTab) => {
      setError("");
      const nextParams = new URLSearchParams(searchParams);
      if (next === "scenarios") {
        nextParams.delete("tab");
      } else {
        nextParams.set("tab", next);
      }
      setSearchParams(nextParams, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowTemplate[]>([]);
  const [agents, setAgents] = useState<AgentTemplate[]>([]);
  const [builderLoaded, setBuilderLoaded] = useState(false);
  const [form, setForm] = useState({
    id: "",
    name: "",
    description: "",
    scenario: "custom",
    agent_ids: "",
  });

  const agentPlaceholder = useMemo(() => agents.map((agent) => agent.id).join(", "), [agents]);

  const loadScenarios = useCallback(async () => {
    const items = await listScenarios();
    setScenarios(items);
  }, []);

  const loadBuilder = useCallback(async () => {
    const [workflowItems, agentItems] = await Promise.all([listWorkflowTemplates(), listAgentTemplates()]);
    setWorkflows(workflowItems);
    setAgents(agentItems);
    setBuilderLoaded(true);
  }, []);

  useEffect(() => {
    loadScenarios().catch((err: unknown) => setError(String(err)));
  }, [loadScenarios]);

  useEffect(() => {
    if (activeTab !== "builder" || builderLoaded) {
      return;
    }
    loadBuilder().catch((err: unknown) => setError(String(err)));
  }, [activeTab, builderLoaded, loadBuilder]);

  async function refreshAfterMutation() {
    await loadScenarios();
    if (builderLoaded || activeTab === "builder") {
      await loadBuilder();
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const agentIds = splitList(form.agent_ids);
    try {
      await createWorkflowTemplate({
        id: form.id || undefined,
        name: form.name,
        description: form.description,
        scenario: form.scenario,
        status: "draft",
        version: 1,
        graph: graphFromAgents(agentIds),
      });
      setForm({ id: "", name: "", description: "", scenario: "custom", agent_ids: "" });
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
        ? "该场景已发布，删除后「使用场景」中将不再出现。确定删除吗？"
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
    activeTab === "scenarios"
      ? "选择已发布场景，一键创建绑定公司的尽调应用。"
      : activeTab === "builder"
        ? "新建草稿、编排 Agent、发布后与「使用场景」页同步可见；可删除自建模板（内置场景除外）。"
        : "维护提示词、Skill 包、工具与资源配置，供流程模板引用。";

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Workflows</p>
        <h1>场景与Agent</h1>
        <p>{heroDescription}</p>
        <nav className="hub-tab-bar" aria-label="工作流分区">
          <button
            type="button"
            className="hub-tab"
            aria-current={activeTab === "scenarios" ? "page" : undefined}
            onClick={() => setActiveTab("scenarios")}
          >
            使用场景
          </button>
          <button
            type="button"
            className="hub-tab"
            aria-current={activeTab === "builder" ? "page" : undefined}
            onClick={() => setActiveTab("builder")}
          >
            场景管理
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

      {activeTab === "scenarios" ? (
        <SectionCard title="已发布场景" description="可直接绑定目标公司并创建应用。">
          <div className="scenario-grid">
            {scenarios.map((scenario) => (
              <SectionCard key={scenario.id} title={scenario.name} description={scenario.description}>
                <div className="tag-row">
                  <span>{scenario.scenario}</span>
                  <span>{scenario.agents.length} agents</span>
                </div>
                <ol className="agent-chain">
                  {scenario.agents.map((agent) => (
                    <li key={`${scenario.id}-${agent}`}>{agent}</li>
                  ))}
                </ol>
                <Link className="button-link" to={`/projects/new?workflow=${scenario.id}`}>
                  应用到公司
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
                <SectionCard title="新增流程模板" description="逗号分隔 Agent 顺序；保存为草稿后在此页发布。">
                  <form className="form" onSubmit={handleSubmit}>
                    <label>
                      ID
                      <input value={form.id} onChange={(event) => setForm({ ...form, id: event.target.value })} />
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
                      Agent 串流顺序
                      <input
                        placeholder={agentPlaceholder}
                        value={form.agent_ids}
                        onChange={(event) => setForm({ ...form, agent_ids: event.target.value })}
                      />
                    </label>
                    <label>
                      描述
                      <input
                        value={form.description}
                        onChange={(event) => setForm({ ...form, description: event.target.value })}
                      />
                    </label>
                    <button type="submit">保存为草稿</button>
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
                        {workflow.graph.nodes.map((node) => (
                          <li key={node.id}>{node.agent_template_id}</li>
                        ))}
                      </ol>
                      <div className="row-actions">
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
