import { FormEvent, useEffect, useState } from "react";

import { createAgentTemplate, listAgentTemplates, listResourceConfigs, listSkills } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import type { AgentTemplate, ResourceConfig, SkillConfig } from "../types/domain";

function splitList(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

export function AgentTemplatesPage() {
  const [agents, setAgents] = useState<AgentTemplate[]>([]);
  const [skills, setSkills] = useState<SkillConfig[]>([]);
  const [resources, setResources] = useState<ResourceConfig[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    id: "",
    name: "",
    role: "",
    prompt: "",
    skill_ids: "",
    resource_ids: "",
    output_schema: "agent_result",
  });

  async function refresh() {
    const [agentItems, skillItems, resourceItems] = await Promise.all([
      listAgentTemplates(),
      listSkills(),
      listResourceConfigs(),
    ]);
    setAgents(agentItems);
    setSkills(skillItems);
    setResources(resourceItems);
  }

  useEffect(() => {
    refresh().catch((err: unknown) => setError(String(err)));
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      await createAgentTemplate({
        id: form.id || undefined,
        name: form.name,
        role: form.role,
        prompt: form.prompt,
        skill_ids: splitList(form.skill_ids),
        resource_ids: splitList(form.resource_ids),
        output_schema: form.output_schema,
        enabled: true,
      });
      setForm({ id: "", name: "", role: "", prompt: "", skill_ids: "", resource_ids: "", output_schema: "agent_result" });
      await refresh();
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Agent Templates</p>
        <h1>Agent 配置管理</h1>
        <p>配置每个 agent 的角色、提示词、skills、数据资源和输出 schema，再组合进流程模板。</p>
      </header>
      {error ? <div className="error">{error}</div> : null}
      <div className="grid two">
        <SectionCard title="新增 Agent 模板">
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
              角色
              <input value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })} />
            </label>
            <label>
              Skills，逗号分隔
              <input
                placeholder={skills.map((skill) => skill.id).join(", ")}
                value={form.skill_ids}
                onChange={(event) => setForm({ ...form, skill_ids: event.target.value })}
              />
            </label>
            <label>
              资源，逗号分隔
              <input
                placeholder={resources.map((resource) => resource.id).join(", ")}
                value={form.resource_ids}
                onChange={(event) => setForm({ ...form, resource_ids: event.target.value })}
              />
            </label>
            <label>
              提示词
              <textarea value={form.prompt} onChange={(event) => setForm({ ...form, prompt: event.target.value })} />
            </label>
            <button>保存 Agent 模板</button>
          </form>
        </SectionCard>
        <SectionCard title="Agent 模板列表">
          <ul className="list">
            {agents.map((agent) => (
              <li key={agent.id}>
                <span>{agent.role}</span>
                <strong>{agent.name}</strong>
                <p>Skills: {agent.skill_ids.join(", ") || "未配置"}</p>
                <p>Resources: {agent.resource_ids.join(", ") || "未配置"}</p>
              </li>
            ))}
          </ul>
        </SectionCard>
      </div>
    </div>
  );
}
