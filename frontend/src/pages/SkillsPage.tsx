import { FormEvent, useEffect, useState } from "react";

import { createSkill, listSkills } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import type { SkillPackage } from "../types/domain";

export function SkillsPage() {
  const [skills, setSkills] = useState<SkillPackage[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    id: "",
    name: "",
    description: "",
    directory_name: "",
    skill_md: "---\nname: due-diligence-example\ndescription: Guides a due diligence workflow. Use when this agent needs domain-specific diligence instructions.\n---\n\n# Due Diligence Example\n\nUse evidence-backed findings and preserve uncertainty.\n",
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
        directory_name: form.directory_name,
        skill_md: form.skill_md,
        resources_manifest: { files: ["SKILL.md"], references: [], scripts: [], assets: [] },
        enabled: true,
      });
      setForm({
        id: "",
        name: "",
        description: "",
        directory_name: "",
        skill_md: "---\nname: due-diligence-example\ndescription: Guides a due diligence workflow. Use when this agent needs domain-specific diligence instructions.\n---\n\n# Due Diligence Example\n\nUse evidence-backed findings and preserve uncertainty.\n",
      });
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
        <p>管理 Anthropic/Cursor 风格的 Skill 包：每个 Skill 都是一个目录，核心内容是 `SKILL.md`，可附带 references、scripts、assets 等资源。</p>
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
              目录名
              <input value={form.directory_name} onChange={(event) => setForm({ ...form, directory_name: event.target.value })} />
            </label>
            <label>
              描述
              <input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
            </label>
            <label>
              SKILL.md
              <textarea value={form.skill_md} onChange={(event) => setForm({ ...form, skill_md: event.target.value })} />
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
                <small>{skill.directory_name}/SKILL.md</small>
              </li>
            ))}
          </ul>
        </SectionCard>
      </div>
    </div>
  );
}
