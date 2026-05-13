import { FormEvent, useEffect, useState } from "react";

import { createAgentTemplate, listAgentTemplates, listResourceConfigs, listSkills, listToolConfigs } from "../api/client";
import { SectionCard } from "./SectionCard";
import type { AgentTemplate, ResourceConfig, SkillPackage, ToolConfig } from "../types/domain";

function splitList(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

const defaultReActConfig = JSON.stringify(
  {
    max_iters: 6,
    parallel_tool_calls: false,
    model: {
      baseUrl: "http://127.0.0.1:8081/v1",
      apiKey: "yuanjun",
      api: "anthropic-messages",
      models: [
        {
          id: "kimi-code",
          name: "kimi-code(Custom Provider)",
          reasoning: true,
          input: ["text", "image"],
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
          contextWindow: 128000,
          maxTokens: 4096,
        },
      ],
    },
  },
  null,
  2,
);

type AgentTemplatesPanelProps = {
  /** 新建或更新 Agent 后通知父级（例如在「流程管理」中刷新可选 Agent 列表） */
  onAgentsChanged?: () => void;
};

export function AgentTemplatesPanel({ onAgentsChanged }: AgentTemplatesPanelProps) {
  const [agents, setAgents] = useState<AgentTemplate[]>([]);
  const [skills, setSkills] = useState<SkillPackage[]>([]);
  const [tools, setTools] = useState<ToolConfig[]>([]);
  const [resources, setResources] = useState<ResourceConfig[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    id: "",
    name: "",
    role: "",
    prompt: "",
    skill_package_ids: "",
    tool_ids: "",
    resource_ids: "",
    react_config: defaultReActConfig,
    output_schema: "agent_result",
  });

  async function refresh() {
    const [agentItems, skillItems, toolItems, resourceItems] = await Promise.all([
      listAgentTemplates(),
      listSkills(),
      listToolConfigs(),
      listResourceConfigs(),
    ]);
    setAgents(agentItems);
    setSkills(skillItems);
    setTools(toolItems);
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
        skill_package_ids: splitList(form.skill_package_ids),
        tool_ids: splitList(form.tool_ids),
        skill_ids: splitList(form.tool_ids),
        resource_ids: splitList(form.resource_ids),
        react_config: JSON.parse(form.react_config) as Record<string, unknown>,
        output_schema: form.output_schema,
        enabled: true,
      });
      setForm({
        id: "",
        name: "",
        role: "",
        prompt: "",
        skill_package_ids: "",
        tool_ids: "",
        resource_ids: "",
        react_config: defaultReActConfig,
        output_schema: "agent_result",
      });
      await refresh();
      onAgentsChanged?.();
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <>
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
              Anthropic Skills，逗号分隔
              <input
                placeholder={skills.map((skill) => skill.id).join(", ")}
                value={form.skill_package_ids}
                onChange={(event) => setForm({ ...form, skill_package_ids: event.target.value })}
              />
            </label>
            <label>
              工具，逗号分隔
              <input
                placeholder={tools.map((tool) => tool.id).join(", ")}
                value={form.tool_ids}
                onChange={(event) => setForm({ ...form, tool_ids: event.target.value })}
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
              AgentScope ReAct 配置 JSON
              <textarea value={form.react_config} onChange={(event) => setForm({ ...form, react_config: event.target.value })} />
            </label>
            <label>
              提示词
              <textarea value={form.prompt} onChange={(event) => setForm({ ...form, prompt: event.target.value })} />
            </label>
            <button type="submit">保存 Agent 模板</button>
          </form>
        </SectionCard>
        <SectionCard title="Agent 模板列表">
          <ul className="list">
            {agents.map((agent) => (
              <li key={agent.id}>
                <span>{agent.role}</span>
                <strong>{agent.name}</strong>
                <p>Skills: {(agent.skill_package_ids ?? []).join(", ") || "未配置"}</p>
                <p>Tools: {(agent.tool_ids ?? agent.skill_ids ?? []).join(", ") || "未配置"}</p>
                <p>Resources: {agent.resource_ids.join(", ") || "未配置"}</p>
                <p>ReAct: max_iters={(agent.react_config?.max_iters as number | undefined) ?? 6}</p>
              </li>
            ))}
          </ul>
        </SectionCard>
      </div>
    </>
  );
}
