import { FormEvent, useEffect, useState } from "react";

import { createSkill, listSkills } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import type { SkillConfig } from "../types/domain";

export function SkillsPage() {
  const [skills, setSkills] = useState<SkillConfig[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    id: "",
    name: "",
    description: "",
    implementation: "",
  });

  async function refresh() {
    setSkills(await listSkills());
  }

  useEffect(() => {
    refresh().catch((err: unknown) => setError(String(err)));
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      await createSkill({
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
        <p className="eyebrow">Skill Registry</p>
        <h1>Skills 配置管理</h1>
        <p>管理 Agent 可调用的通用能力，例如搜索、网页抓取、文件解析、向量检索和报告存储。</p>
      </header>
      {error ? <div className="error">{error}</div> : null}
      <div className="grid two">
        <SectionCard title="新增 Skill">
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
            <button>保存 Skill</button>
          </form>
        </SectionCard>
        <SectionCard title="可用 Skills">
          <ul className="list">
            {skills.map((skill) => (
              <li key={skill.id}>
                <span>{skill.enabled ? "enabled" : "disabled"}</span>
                <strong>{skill.name}</strong>
                <p>{skill.description}</p>
                <small>{skill.implementation}</small>
              </li>
            ))}
          </ul>
        </SectionCard>
      </div>
    </div>
  );
}
