import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  cloneWorkflowTemplate,
  createWorkflowTemplate,
  listAgentTemplates,
  listWorkflowTemplates,
  publishWorkflowTemplate,
} from "../api/client";
import { SectionCard } from "../components/SectionCard";
import type { AgentTemplate, WorkflowGraph, WorkflowTemplate } from "../types/domain";

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

export function WorkflowTemplatesPage() {
  const [workflows, setWorkflows] = useState<WorkflowTemplate[]>([]);
  const [agents, setAgents] = useState<AgentTemplate[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    id: "",
    name: "",
    description: "",
    scenario: "custom",
    agent_ids: "",
  });

  const agentPlaceholder = useMemo(() => agents.map((agent) => agent.id).join(", "), [agents]);

  async function refresh() {
    const [workflowItems, agentItems] = await Promise.all([listWorkflowTemplates(), listAgentTemplates()]);
    setWorkflows(workflowItems);
    setAgents(agentItems);
  }

  useEffect(() => {
    refresh().catch((err: unknown) => setError(String(err)));
  }, []);

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
      await refresh();
    } catch (err) {
      setError(String(err));
    }
  }

  async function handlePublish(workflowId: string) {
    setError("");
    try {
      await publishWorkflowTemplate(workflowId);
      await refresh();
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleClone(workflowId: string) {
    setError("");
    try {
      await cloneWorkflowTemplate(workflowId);
      await refresh();
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Workflow Builder</p>
        <h1>任务流程模板配置</h1>
        <p>配置多个 agent 的串流流程。模板发布后，可被下游不同公司的尽调任务复用。</p>
      </header>
      {error ? <div className="error">{error}</div> : null}
      <div className="grid two">
        <SectionCard title="新增流程模板" description="MVP 先使用逗号分隔的 agent 顺序配置串流。">
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
              <input value={form.scenario} onChange={(event) => setForm({ ...form, scenario: event.target.value })} />
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
              <input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
            </label>
            <button>保存为草稿</button>
          </form>
        </SectionCard>
        <SectionCard title="可用 Agent">
          <ul className="list">
            {agents.map((agent) => (
              <li key={agent.id}>
                <span>{agent.output_schema}</span>
                <strong>{agent.id}</strong>
                <p>{agent.role}</p>
              </li>
            ))}
          </ul>
        </SectionCard>
      </div>
      <SectionCard title="流程模板列表">
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
                <button onClick={() => handlePublish(workflow.id)}>发布</button>
                <button className="secondary-button" onClick={() => handleClone(workflow.id)}>
                  克隆
                </button>
              </div>
            </article>
          ))}
        </div>
      </SectionCard>
    </div>
  );
}
