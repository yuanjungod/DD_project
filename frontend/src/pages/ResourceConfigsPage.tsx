import { FormEvent, useEffect, useState } from "react";

import { createResourceConfig, listResourceConfigs } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import type { ResourceConfig } from "../types/domain";

export function ResourceConfigsPage() {
  const [resources, setResources] = useState<ResourceConfig[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ id: "", name: "", type: "web", description: "" });

  async function refresh() {
    setResources(await listResourceConfigs());
  }

  useEffect(() => {
    refresh().catch((err: unknown) => setError(String(err)));
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      await createResourceConfig({
        id: form.id || undefined,
        name: form.name,
        type: form.type,
        description: form.description,
        connection_config: {},
        enabled: true,
      });
      setForm({ id: "", name: "", type: "web", description: "" });
      await refresh();
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Resource Registry</p>
        <h1>可用资源配置管理</h1>
        <p>管理可被 Agent 使用的数据源，例如公开网页、文件库、向量库、业务数据库和外部 API。</p>
      </header>
      {error ? <div className="error">{error}</div> : null}
      <div className="grid two">
        <SectionCard title="新增资源">
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
              类型
              <select value={form.type} onChange={(event) => setForm({ ...form, type: event.target.value })}>
                <option value="web">公开网页</option>
                <option value="file_store">文件库</option>
                <option value="vector_store">向量库</option>
                <option value="database">业务数据库</option>
                <option value="api">外部 API</option>
              </select>
            </label>
            <label>
              描述
              <input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
            </label>
            <button>保存资源</button>
          </form>
        </SectionCard>
        <SectionCard title="可用资源">
          <ul className="list">
            {resources.map((resource) => (
              <li key={resource.id}>
                <span>{resource.type}</span>
                <strong>{resource.name}</strong>
                <p>{resource.description}</p>
              </li>
            ))}
          </ul>
        </SectionCard>
      </div>
    </div>
  );
}
