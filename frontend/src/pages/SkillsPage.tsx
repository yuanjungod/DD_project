import { FormEvent, useEffect, useState } from "react";

import { createSkill, debugSkillDraft, getSkill, listSkills, updateSkill } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import type { SkillDebugResult, SkillPackage } from "../types/domain";

const defaultSkillMd =
  "---\nname: due-diligence-example\ndescription: Guides a due diligence workflow. Use when this agent needs domain-specific diligence instructions.\n---\n\n# Due Diligence Example\n\nUse evidence-backed findings and preserve uncertainty.\n";

const defaultManifest = JSON.stringify({ files: ["SKILL.md"], references: [], scripts: [], assets: [] }, null, 2);

export function SkillsPage() {
  const [skills, setSkills] = useState<SkillPackage[]>([]);
  const [selectedSkillId, setSelectedSkillId] = useState("");
  const [debugResult, setDebugResult] = useState<SkillDebugResult | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState({
    id: "",
    name: "",
    description: "",
    directory_name: "",
    skill_md: defaultSkillMd,
    resources_manifest: defaultManifest,
    enabled: true,
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
    setNotice("");
    try {
      const payload = {
        name: form.name,
        description: form.description,
        directory_name: form.directory_name,
        skill_md: form.skill_md,
        resources_manifest: JSON.parse(form.resources_manifest) as Record<string, unknown>,
        enabled: form.enabled,
      };
      const existing = skills.some((skill) => skill.id === form.id);
      const saved = existing
        ? await updateSkill(form.id, payload)
        : await createSkill({ ...payload, id: form.id || undefined });
      setSelectedSkillId(saved.id);
      setNotice(existing ? "Skill 已更新" : "Skill 已创建");
      await refresh();
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleSelect(skillId: string) {
    setError("");
    setNotice("");
    setDebugResult(null);
    try {
      const skill = await getSkill(skillId);
      setSelectedSkillId(skill.id);
      setForm({
        id: skill.id,
        name: skill.name,
        description: skill.description,
        directory_name: skill.directory_name,
        skill_md: skill.skill_md,
        resources_manifest: JSON.stringify(skill.resources_manifest ?? {}, null, 2),
        enabled: skill.enabled,
      });
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleDebug() {
    setError("");
    setNotice("");
    try {
      const result = await debugSkillDraft({
        id: form.id || undefined,
        name: form.name,
        description: form.description,
        directory_name: form.directory_name,
        skill_md: form.skill_md,
        resources_manifest: JSON.parse(form.resources_manifest) as Record<string, unknown>,
        enabled: form.enabled,
      });
      setDebugResult(result);
      setNotice(result.valid ? "Skill 调试通过" : "Skill 调试发现问题");
    } catch (err) {
      setError(String(err));
    }
  }

  function handleNewSkill() {
    setSelectedSkillId("");
    setDebugResult(null);
    setNotice("");
    setError("");
    setForm({
      id: "",
      name: "",
      description: "",
      directory_name: "",
      skill_md: defaultSkillMd,
      resources_manifest: defaultManifest,
      enabled: true,
    });
  }

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Skill Registry</p>
        <h1>Skills 配置管理</h1>
        <p>查看、修改和调试 Anthropic/Cursor 风格的 Skill 包：每个 Skill 都是一个目录，核心内容是 `SKILL.md`，可附带 references、scripts、assets 等资源。</p>
      </header>
      {error ? <div className="error">{error}</div> : null}
      {notice ? <div className="notice">{notice}</div> : null}
      <div className="grid two">
        <SectionCard title="可用 Skills">
          <div className="row-actions">
            <button type="button" onClick={handleNewSkill}>新增 Skill</button>
          </div>
          <ul className="list">
            {skills.map((skill) => (
              <li className={skill.id === selectedSkillId ? "selected-list-item" : ""} key={skill.id}>
                <span>{skill.enabled ? "enabled" : "disabled"}</span>
                <strong>{skill.name}</strong>
                <p>{skill.description}</p>
                <small>{skill.directory_name}/SKILL.md</small>
                <div className="row-actions">
                  <button type="button" className="secondary-button" onClick={() => handleSelect(skill.id)}>
                    查看/编辑
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </SectionCard>
        <SectionCard title={selectedSkillId ? "查看 / 修改 / 调试 Skill" : "新增 / 调试 Skill"}>
          <form className="form" onSubmit={handleSubmit}>
            <label>
              ID
              <input
                disabled={Boolean(selectedSkillId)}
                value={form.id}
                onChange={(event) => setForm({ ...form, id: event.target.value })}
              />
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
              启用
              <select
                value={String(form.enabled)}
                onChange={(event) => setForm({ ...form, enabled: event.target.value === "true" })}
              >
                <option value="true">enabled</option>
                <option value="false">disabled</option>
              </select>
            </label>
            <label>
              SKILL.md
              <textarea
                className="code-editor"
                value={form.skill_md}
                onChange={(event) => setForm({ ...form, skill_md: event.target.value })}
              />
            </label>
            <label>
              resources_manifest JSON
              <textarea
                className="code-editor small"
                value={form.resources_manifest}
                onChange={(event) => setForm({ ...form, resources_manifest: event.target.value })}
              />
            </label>
            <div className="row-actions">
              <button type="submit">{selectedSkillId ? "保存修改" : "保存 Skill"}</button>
              <button type="button" className="secondary-button" onClick={handleDebug}>
                调试当前内容
              </button>
            </div>
          </form>
          {debugResult ? (
            <div className={debugResult.valid ? "debug-panel valid" : "debug-panel invalid"}>
              <strong>{debugResult.valid ? "调试通过" : "调试未通过"}</strong>
              <div>
                <p>Checks</p>
                <ul>
                  {debugResult.checks.map((check) => <li key={check}>{check}</li>)}
                </ul>
              </div>
              {debugResult.errors.length ? (
                <div>
                  <p>Errors</p>
                  <ul>
                    {debugResult.errors.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              ) : null}
              <label>
                AgentScope Skill Prompt Preview
                <textarea readOnly className="code-editor small" value={debugResult.agent_skill_prompt ?? ""} />
              </label>
            </div>
          ) : null}
        </SectionCard>
      </div>
    </div>
  );
}
