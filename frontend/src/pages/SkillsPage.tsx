import { FormEvent, useEffect, useRef, useState } from "react";

import { createSkill, debugSkillDraft, deleteSkill, getSkill, importSkillZip, listSkills, updateSkill } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import type { SkillDebugResult, SkillPackage } from "../types/domain";

const defaultSkillMd =
  "---\nname: due-diligence-example\ndescription: Guides a due diligence workflow. Use when this agent needs domain-specific diligence instructions.\n---\n\n# Due Diligence Example\n\nUse source-backed findings and preserve uncertainty.\n";

const defaultPackageFiles = {
  "references/source-guidance.md": "# Source Guidance\n\nAdd reference notes for this skill here.\n",
};

const defaultManifest = JSON.stringify(
  {
    files: ["SKILL.md", ...Object.keys(defaultPackageFiles)],
    references: ["references/source-guidance.md"],
    scripts: [],
    assets: [],
  },
  null,
  2,
);

export function SkillsPage() {
  const zipInputRef = useRef<HTMLInputElement>(null);
  const [zipDirOverride, setZipDirOverride] = useState("");
  const [zipUploading, setZipUploading] = useState(false);
  const [deletingSkillId, setDeletingSkillId] = useState("");
  const [skills, setSkills] = useState<SkillPackage[]>([]);
  const [selectedSkillId, setSelectedSkillId] = useState("");
  const [view, setView] = useState<"list" | "editor">("list");
  const [selectedFilePath, setSelectedFilePath] = useState("SKILL.md");
  const [newFilePath, setNewFilePath] = useState("");
  const [debugResult, setDebugResult] = useState<SkillDebugResult | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState({
    id: "",
    name: "",
    description: "",
    directory_name: "",
    skill_md: defaultSkillMd,
    package_files: defaultPackageFiles as Record<string, string>,
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
        package_files: form.package_files,
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
      setView("editor");
      setForm({
        id: skill.id,
        name: skill.name,
        description: skill.description,
        directory_name: skill.directory_name,
        skill_md: skill.skill_md,
        package_files: skill.package_files ?? {},
        resources_manifest: JSON.stringify(skill.resources_manifest ?? {}, null, 2),
        enabled: skill.enabled,
      });
      setSelectedFilePath("SKILL.md");
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
        package_files: form.package_files,
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
      package_files: defaultPackageFiles,
      resources_manifest: defaultManifest,
      enabled: true,
    });
    setSelectedFilePath("SKILL.md");
    setView("editor");
  }

  async function handleDeleteSkill(skill: SkillPackage) {
    const ok = window.confirm(
      `确定删除 Skill「${skill.name}」（${skill.directory_name}）吗？将删除 agent_service/skills/${skill.directory_name}/ 下的全部文件，且不可恢复。`,
    );
    if (!ok) return;
    setError("");
    setNotice("");
    setDeletingSkillId(skill.id);
    try {
      await deleteSkill(skill.id);
      if (selectedSkillId === skill.id) {
        setSelectedSkillId("");
        setView("list");
      }
      setNotice(`已删除 Skill「${skill.name}」`);
      await refresh();
    } catch (err: unknown) {
      setError(String(err));
    } finally {
      setDeletingSkillId("");
    }
  }

  function filePaths(): string[] {
    return ["SKILL.md", ...Object.keys(form.package_files).sort()];
  }

  function selectedFileContent(): string {
    return selectedFilePath === "SKILL.md" ? form.skill_md : form.package_files[selectedFilePath] ?? "";
  }

  function updateSelectedFileContent(content: string) {
    if (selectedFilePath === "SKILL.md") {
      setForm({ ...form, skill_md: content });
      return;
    }
    setForm({
      ...form,
      package_files: { ...form.package_files, [selectedFilePath]: content },
    });
  }

  function handleAddFile() {
    const filePath = newFilePath.trim();
    if (!filePath || filePath === "SKILL.md") {
      return;
    }
    setForm({
      ...form,
      package_files: {
        ...form.package_files,
        [filePath]: form.package_files[filePath] ?? "",
      },
      resources_manifest: addFileToManifest(form.resources_manifest, filePath),
    });
    setSelectedFilePath(filePath);
    setNewFilePath("");
  }

  function handleDeleteSelectedFile() {
    if (selectedFilePath === "SKILL.md") {
      return;
    }
    const nextFiles = { ...form.package_files };
    delete nextFiles[selectedFilePath];
    setForm({
      ...form,
      package_files: nextFiles,
      resources_manifest: removeFileFromManifest(form.resources_manifest, selectedFilePath),
    });
    setSelectedFilePath("SKILL.md");
  }

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Skill Registry</p>
        <h1>Skills 配置管理</h1>
        <p>
          查看、修改和调试 Anthropic/Cursor 风格的 Skill 包：每个 Skill 固定同步到{" "}
          <code>agent_service/skills/&lt;directory&gt;/</code>，核心内容是 <code>SKILL.md</code>
          ，可附带 references、scripts、assets；也可<strong>上传 .zip</strong>
          （单顶层目录包住 <code>SKILL.md</code> 与同包资源）一键入库。
        </p>
      </header>
      {error ? <div className="error">{error}</div> : null}
      {notice ? <div className="notice">{notice}</div> : null}
      {view === "list" ? (
        <SectionCard title="可用 Skills">
          <div className="skill-list-header">
            <div>
              <strong>{skills.length} 个 Skill 包</strong>
              <p>选择一个 Skill 进入独立的查看、修改和调试页面；或直接上传 Cursor/Anthropic 导出的 Skill 压缩包。</p>
            </div>
            <div className="skill-upload-toolbar">
              <input
                ref={zipInputRef}
                type="file"
                accept=".zip,application/zip"
                hidden
                aria-hidden
                onChange={async (event) => {
                  const picked = event.target.files?.[0];
                  event.target.value = "";
                  if (!picked) return;
                  setError("");
                  setNotice("");
                  setZipUploading(true);
                  try {
                    const saved = await importSkillZip(picked, zipDirOverride.trim() ? zipDirOverride : undefined);
                    setNotice(`已从 ZIP 创建 Skill「${saved.name}」(${saved.directory_name})`);
                    setZipDirOverride("");
                    await refresh();
                  } catch (err: unknown) {
                    setError(String(err));
                  } finally {
                    setZipUploading(false);
                  }
                }}
              />
              <label className="skill-zip-dir-label">
                目录名（可选）
                <input
                  className="skill-zip-dir-input"
                  placeholder="覆盖 SKILL 目录名（英文短横杠）"
                  value={zipDirOverride}
                  onChange={(e) => setZipDirOverride(e.target.value)}
                />
              </label>
              <button
                type="button"
                className="secondary-button"
                disabled={zipUploading}
                onClick={() => zipInputRef.current?.click()}
              >
                {zipUploading ? "上传中…" : "上传 ZIP 压缩包"}
              </button>
              <button type="button" disabled={zipUploading} onClick={handleNewSkill}>
                新增 Skill
              </button>
            </div>
          </div>
          <ul className="skill-card-list">
            {skills.map((skill) => (
              <li key={skill.id}>
                <div>
                  <span>{skill.enabled ? "enabled" : "disabled"}</span>
                  <strong>{skill.name}</strong>
                  <p>{skill.description}</p>
                  <small>agent_service/skills/{skill.directory_name}/</small>
                </div>
                <div className="skill-card-actions">
                  <button type="button" className="secondary-button" onClick={() => handleSelect(skill.id)}>
                    进入配置
                  </button>
                  <button
                    type="button"
                    className="danger-button"
                    disabled={deletingSkillId === skill.id}
                    onClick={() => void handleDeleteSkill(skill)}
                  >
                    {deletingSkillId === skill.id ? "删除中…" : "删除"}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </SectionCard>
      ) : (
        <div className="skill-editor-stack">
          <div className="detail-toolbar">
            <button type="button" className="secondary-button" onClick={() => setView("list")}>
              返回 Skills 列表
            </button>
            <div>
              <span>{selectedSkillId ? "编辑 Skill" : "新增 Skill"}</span>
              <strong>{form.name || form.id || "未命名 Skill"}</strong>
              <small>agent_service/skills/{form.directory_name || "<directory>"}/</small>
            </div>
            {selectedSkillId ? (
              <button
                type="button"
                className="danger-button"
                disabled={Boolean(deletingSkillId)}
                onClick={() => {
                  const skill = skills.find((item) => item.id === selectedSkillId);
                  if (skill) void handleDeleteSkill(skill);
                }}
              >
                {deletingSkillId === selectedSkillId ? "删除中…" : "删除 Skill"}
              </button>
            ) : null}
          </div>
          <SectionCard title="基础信息">
            <form className="form" onSubmit={handleSubmit}>
              <div className="grid two">
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
                  启用
                  <select
                    value={String(form.enabled)}
                    onChange={(event) => setForm({ ...form, enabled: event.target.value === "true" })}
                  >
                    <option value="true">enabled</option>
                    <option value="false">disabled</option>
                  </select>
                </label>
              </div>
              <label>
                描述
                <input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
              </label>
              <div className="skill-file-workspace">
                <div className="skill-file-sidebar">
                  <strong>Skill 文件</strong>
                  <div className="skill-file-list">
                    {filePaths().map((filePath) => (
                      <button
                        type="button"
                        className={filePath === selectedFilePath ? "skill-file-tab active" : "skill-file-tab"}
                        key={filePath}
                        onClick={() => setSelectedFilePath(filePath)}
                      >
                        {filePath}
                      </button>
                    ))}
                  </div>
                  <div className="file-create-row">
                    <input
                      placeholder="references/checklist.md"
                      value={newFilePath}
                      onChange={(event) => setNewFilePath(event.target.value)}
                    />
                    <button type="button" className="secondary-button" onClick={handleAddFile}>
                      添加文件
                    </button>
                  </div>
                </div>
                <label className="skill-file-editor">
                  {selectedFilePath}
                  <textarea
                    className="code-editor"
                    value={selectedFileContent()}
                    onChange={(event) => updateSelectedFileContent(event.target.value)}
                  />
                  {selectedFilePath !== "SKILL.md" ? (
                    <button type="button" className="secondary-button" onClick={handleDeleteSelectedFile}>
                      删除当前文件
                    </button>
                  ) : null}
                </label>
              </div>
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
          </SectionCard>
          {debugResult ? (
            <SectionCard title="调试结果">
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
            </SectionCard>
          ) : null}
        </div>
      )}
    </div>
  );
}

function addFileToManifest(manifestJson: string, filePath: string): string {
  try {
    const manifest = JSON.parse(manifestJson) as { files?: unknown };
    const files = Array.isArray(manifest.files) ? manifest.files.filter((item): item is string => typeof item === "string") : [];
    return JSON.stringify({ ...manifest, files: Array.from(new Set([...files, filePath])) }, null, 2);
  } catch {
    return manifestJson;
  }
}

function removeFileFromManifest(manifestJson: string, filePath: string): string {
  try {
    const manifest = JSON.parse(manifestJson) as { files?: unknown };
    const files = Array.isArray(manifest.files) ? manifest.files.filter((item) => item !== filePath) : manifest.files;
    return JSON.stringify({ ...manifest, files }, null, 2);
  } catch {
    return manifestJson;
  }
}
