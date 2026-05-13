import { FormEvent, useEffect, useState } from "react";

import { createToolConfig, listToolConfigs } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import type { ToolConfig } from "../types/domain";

export function ToolConfigsPage() {
  const [tools, setTools] = useState<ToolConfig[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    id: "",
    name: "",
    description: "",
    implementation: "",
  });

  async function refresh() {
    setTools(await listToolConfigs());
  }

  useEffect(() => {
    refresh().catch((err: unknown) => setError(String(err)));
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      await createToolConfig({
        id: form.id || undefined,
        name: form.name,
        description: form.description,
        implementation: form.implementation,
        input_schema: {},
        output_schema: {},
        requires_api_key: false,
        enabled: true,
      });
      setForm({ id: "", name: "", description: "", implementation: "" });
      await refresh();
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Tool Registry</p>
        <h1>工具配置管理</h1>
        <p>管理 Agent 可调用的执行工具，例如搜索、网页抓取、文件解析、向量检索、证据存储和报告存储。</p>
      </header>
      {error ? <div className="error">{error}</div> : null}
      <div className="grid two">
        <SectionCard title="新增工具">
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
              实现路径
              <input value={form.implementation} onChange={(event) => setForm({ ...form, implementation: event.target.value })} />
            </label>
            <label>
              描述
              <input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
            </label>
            <button>保存工具</button>
          </form>
        </SectionCard>
        <SectionCard title="可用工具">
          <ul className="list">
            {tools.map((tool) => (
              <li key={tool.id}>
                <span>{tool.enabled ? "enabled" : "disabled"}</span>
                <strong>{tool.name}</strong>
                <p>{tool.description}</p>
                <small>{tool.implementation}</small>
              </li>
            ))}
          </ul>
        </SectionCard>
      </div>
    </div>
  );
}
