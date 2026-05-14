import { FormEvent, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  createAgentTemplate,
  listAgentTemplates,
  listLibraryUploads,
  listResourceConfigs,
  listSkills,
  listToolConfigs,
} from "../api/client";
import {
  KNOWN_PLATFORM_RESOURCE_TYPES,
  PLATFORM_RESOURCE_TYPE_OPTIONS,
  type PlatformResourceType,
  type ResourceListFilter,
  isKnownPlatformResourceType,
  resourceListFilterLabel,
} from "../domain/platformResourceRegistry";
import { SectionCard } from "./SectionCard";
import type { AgentTemplate, LibraryFile, ResourceConfig, SkillPackage, ToolConfig } from "../types/domain";

function formatLibraryBytes(n: number): string {
  if (!Number.isFinite(n) || n < 0) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
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

type BindingRow = {
  id: string;
  name: string;
  enabled: boolean;
  hint: string;
};

function SelectableBindingBlock(props: {
  title: string;
  description: string;
  toolbar?: ReactNode;
  filter: string;
  onFilterChange: (value: string) => void;
  items: BindingRow[];
  selected: Set<string>;
  /** When set, overrides badge next to title (e.g. count only selections visible under current tab). */
  selectedCountDisplay?: number;
  onToggle: (id: string) => void;
  emptyText: string;
}) {
  const filtered = useMemo(() => {
    const q = props.filter.trim().toLowerCase();
    if (!q) return props.items;
    return props.items.filter(
      (i) =>
        i.id.toLowerCase().includes(q) ||
        i.name.toLowerCase().includes(q) ||
        i.hint.toLowerCase().includes(q),
    );
  }, [props.items, props.filter]);

  const badgeCount = props.selectedCountDisplay ?? props.selected.size;

  return (
    <section className="agent-binding-section" aria-label={props.title}>
      <div className="agent-binding-section__head">
        <h3 className="agent-binding-section__title">
          {props.title}
          <span className="agent-selected-count">{badgeCount} 项已选</span>
        </h3>
        <p className="agent-binding-section__desc">{props.description}</p>
      </div>
      {props.toolbar ? <div className="agent-binding-toolbar">{props.toolbar}</div> : null}
      <input
        type="search"
        className="agent-binding-filter"
        placeholder="输入关键字筛选…"
        value={props.filter}
        onChange={(e) => props.onFilterChange(e.target.value)}
        aria-label={`${props.title} 筛选`}
      />
      <div className="agent-option-grid">
        {filtered.length === 0 ? (
          <p className="agent-binding-empty">{props.emptyText}</p>
        ) : (
          filtered.map((item) => (
            <label
              key={item.id}
              className={`agent-option-tile ${props.selected.has(item.id) ? "is-selected" : ""} ${!item.enabled ? "is-disabled" : ""}`}
            >
              <input
                type="checkbox"
                checked={props.selected.has(item.id)}
                disabled={!item.enabled}
                onChange={() => {
                  if (item.enabled) props.onToggle(item.id);
                }}
              />
              <div className="agent-option-tile__body">
                <span className="agent-option-tile__title">{item.name}</span>
                {item.hint ? <span className="agent-option-tile__sub">{item.hint}</span> : null}
                <code>{item.id}</code>
              </div>
            </label>
          ))
        )}
      </div>
    </section>
  );
}

function PillRow(props: { label: string; ids: string[]; variant: "skill" | "tool" | "resource" }) {
  if (!props.ids.length) {
    return (
      <p className="agent-catalog-meta">
        <strong>{props.label}</strong>
        <span className="muted">未选择</span>
      </p>
    );
  }
  return (
    <div className="agent-catalog-meta">
      <strong>{props.label}</strong>
      <div className="agent-pill-row">
        {props.ids.map((id) => (
          <span key={id} className={`agent-pill agent-pill--${props.variant}`}>
            {id}
          </span>
        ))}
      </div>
    </div>
  );
}

function typeGroupHeading(typeKey: string): string {
  if (typeKey === "__missing__") return "未在平台列表中";
  if (isKnownPlatformResourceType(typeKey)) {
    return PLATFORM_RESOURCE_TYPE_OPTIONS.find((o) => o.id === typeKey)?.label ?? typeKey;
  }
  return `其他 · ${typeKey}`;
}

function sortResourceTypeGroups(keys: string[]): string[] {
  const known = KNOWN_PLATFORM_RESOURCE_TYPES.filter((k) => keys.includes(k));
  const rest = keys
    .filter((k) => !KNOWN_PLATFORM_RESOURCE_TYPES.includes(k as PlatformResourceType) && k !== "__missing__")
    .sort();
  const tail = keys.includes("__missing__") ? ["__missing__"] : [];
  return [...known, ...rest, ...tail];
}

function ResourceBindingsSummary(props: { ids: string[]; catalog: ResourceConfig[] }) {
  const byId = useMemo(() => new Map(props.catalog.map((r) => [r.id, r])), [props.catalog]);
  const groups = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const id of props.ids) {
      const r = byId.get(id);
      const typeKey = r?.type ?? "__missing__";
      const list = m.get(typeKey) ?? [];
      list.push(id);
      m.set(typeKey, list);
    }
    return m;
  }, [props.ids, byId]);

  if (!props.ids.length) {
    return (
      <p className="agent-catalog-meta">
        <strong>资源</strong>
        <span className="muted">未选择</span>
      </p>
    );
  }

  const ordered = sortResourceTypeGroups([...groups.keys()]);

  return (
    <div className="agent-catalog-meta agent-resource-bindings-summary">
      <strong>资源</strong>
      {ordered.map((typeKey) => (
        <div key={typeKey} className="agent-resource-type-group">
          <span className="agent-resource-type-group__label">{typeGroupHeading(typeKey)}</span>
          <div className="agent-pill-row">
            {(groups.get(typeKey) ?? []).map((id) => (
              <span key={id} className="agent-pill agent-pill--resource">
                {id}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

type AgentTemplatesPanelProps = {
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
    react_config: defaultReActConfig,
  });
  const [skillSel, setSkillSel] = useState<Set<string>>(new Set());
  const [toolSel, setToolSel] = useState<Set<string>>(new Set());
  const [resourceSel, setResourceSel] = useState<Set<string>>(new Set());
  const [skillFilter, setSkillFilter] = useState("");
  const [toolFilter, setToolFilter] = useState("");
  const [resourceFilter, setResourceFilter] = useState("");
  const [resourceKindTab, setResourceKindTab] = useState<ResourceListFilter>("all");
  const [libraryFiles, setLibraryFiles] = useState<LibraryFile[]>([]);
  const [libraryLoadError, setLibraryLoadError] = useState("");
  const [platformFileSel, setPlatformFileSel] = useState<Set<string>>(new Set());

  const toggleSkill = useCallback((id: string) => {
    setSkillSel((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleTool = useCallback((id: string) => {
    setToolSel((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleResource = useCallback((id: string) => {
    setResourceSel((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const togglePlatformFile = useCallback((fileId: string) => {
    setPlatformFileSel((prev) => {
      const next = new Set(prev);
      if (next.has(fileId)) next.delete(fileId);
      else next.add(fileId);
      return next;
    });
  }, []);

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

  useEffect(() => {
    listLibraryUploads()
      .then((rows) => {
        setLibraryFiles(rows);
        setLibraryLoadError("");
      })
      .catch((err: unknown) => setLibraryLoadError(String(err)));
  }, []);

  const fileStoreConnectorSelected = useMemo(
    () =>
      [...resourceSel].some((rid) => {
        const cfg = resources.find((r) => r.id === rid);
        return cfg?.type === "file_store";
      }),
    [resourceSel, resources],
  );

  /** 仅在「全部 / 文件库」标签下展示共享文件区：避免在向量库等标签下仍因已选文件库条目而误显文件列表 */
  const showPlatformFilesPanel =
    fileStoreConnectorSelected && (resourceKindTab === "file_store" || resourceKindTab === "all");

  const resourceSelectedCountForTab = useMemo(() => {
    if (resourceKindTab === "all") return resourceSel.size;
    if (resourceKindTab === "other") {
      return [...resourceSel].filter((rid) => {
        const cfg = resources.find((r) => r.id === rid);
        return cfg != null && !isKnownPlatformResourceType(cfg.type);
      }).length;
    }
    return [...resourceSel].filter((rid) => {
      const cfg = resources.find((r) => r.id === rid);
      return cfg?.type === resourceKindTab;
    }).length;
  }, [resourceKindTab, resourceSel, resources]);

  const skillRows: BindingRow[] = useMemo(
    () =>
      skills.map((s) => ({
        id: s.id,
        name: s.name,
        enabled: s.enabled,
        hint: s.directory_name ? `目录 ${s.directory_name}` : "",
      })),
    [skills],
  );

  const toolRows: BindingRow[] = useMemo(
    () =>
      tools.map((t) => ({
        id: t.id,
        name: t.name,
        enabled: t.enabled,
        hint: t.implementation ? String(t.implementation).slice(0, 48) : "",
      })),
    [tools],
  );

  const resourcesFilteredByKind = useMemo(() => {
    if (resourceKindTab === "all") return resources;
    if (resourceKindTab === "other") return resources.filter((r) => !isKnownPlatformResourceType(r.type));
    return resources.filter((r) => r.type === resourceKindTab);
  }, [resources, resourceKindTab]);

  const showResourceOtherTab = useMemo(
    () => resources.some((r) => !isKnownPlatformResourceType(r.type)) || resourceKindTab === "other",
    [resources, resourceKindTab],
  );

  const resourceRows: BindingRow[] = useMemo(
    () =>
      resourcesFilteredByKind.map((r) => {
        const typeLabel =
          r.type && isKnownPlatformResourceType(r.type)
            ? PLATFORM_RESOURCE_TYPE_OPTIONS.find((o) => o.id === r.type)?.label ?? r.type
            : r.type ?? "";
        return {
          id: r.id,
          name: r.name,
          enabled: r.enabled,
          hint: typeLabel ? `类型 · ${typeLabel}` : "",
        };
      }),
    [resourcesFilteredByKind],
  );

  const resourceKindToolbar = (
    <nav className="resource-kind-tabs agent-binding-resource-tabs" aria-label="平台资源类型">
      <button
        type="button"
        className={`resource-kind-tab ${resourceKindTab === "all" ? "is-active" : ""}`}
        aria-current={resourceKindTab === "all" ? "true" : undefined}
        onClick={() => setResourceKindTab("all")}
      >
        全部
      </button>
      {PLATFORM_RESOURCE_TYPE_OPTIONS.map((o) => (
        <button
          key={o.id}
          type="button"
          className={`resource-kind-tab ${resourceKindTab === o.id ? "is-active" : ""}`}
          aria-current={resourceKindTab === o.id ? "true" : undefined}
          onClick={() => setResourceKindTab(o.id)}
        >
          {o.label}
        </button>
      ))}
      {showResourceOtherTab ? (
        <button
          type="button"
          className={`resource-kind-tab ${resourceKindTab === "other" ? "is-active" : ""}`}
          aria-current={resourceKindTab === "other" ? "true" : undefined}
          onClick={() => setResourceKindTab("other")}
        >
          其他类型
        </button>
      ) : null}
    </nav>
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const toolIds = Array.from(toolSel);
      await createAgentTemplate({
        id: form.id || undefined,
        name: form.name,
        role: form.role,
        prompt: form.prompt,
        skill_package_ids: Array.from(skillSel),
        tool_ids: toolIds,
        skill_ids: toolIds,
        resource_ids: Array.from(resourceSel),
        platform_upload_file_ids: fileStoreConnectorSelected ? Array.from(platformFileSel) : [],
        react_config: JSON.parse(form.react_config) as Record<string, unknown>,
        enabled: true,
      });
      setForm({
        id: "",
        name: "",
        role: "",
        prompt: "",
        react_config: defaultReActConfig,
      });
      setSkillSel(new Set());
      setToolSel(new Set());
      setResourceSel(new Set());
      setSkillFilter("");
      setToolFilter("");
      setResourceFilter("");
      setResourceKindTab("all");
      setPlatformFileSel(new Set());
      await refresh();
      onAgentsChanged?.();
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <>
      {error ? <div className="error">{error}</div> : null}
      <div className="agent-templates-stack">
        <SectionCard
          title="新增 Agent 模板"
          description="勾选 Skills / 工具 / 资源即可绑定；禁用的条目来自后台配置，无法在模板中启用。"
        >
          <form className="form agent-template-editor" onSubmit={handleSubmit}>
            <div className="agent-template-editor__basics">
              <h4 className="agent-template-editor__section-label">基本信息</h4>
              <div className="agent-template-editor__basics-grid">
                <label>
                  ID（可选）
                  <input value={form.id} onChange={(event) => setForm({ ...form, id: event.target.value })} placeholder="留空则自动生成" />
                </label>
                <label>
                  名称 <span className="required-dot">*</span>
                  <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
                </label>
                <label className="agent-template-editor__span-2">
                  角色定位 <span className="required-dot">*</span>
                  <input value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })} placeholder="例如：财务分析专员" required />
                </label>
              </div>
            </div>

            <div className="agent-template-editor__bindings">
              <h4 className="agent-template-editor__section-label">能力与绑定（多选）</h4>
              <SelectableBindingBlock
                title="Skills 包"
                description="Anthropic Skill 目录打包入库的技能；可多选或不选。"
                filter={skillFilter}
                onFilterChange={setSkillFilter}
                items={skillRows}
                selected={skillSel}
                onToggle={toggleSkill}
                emptyText="暂无 Skill 或未匹配筛选条件。"
              />
              <SelectableBindingBlock
                title="工具"
                description="AgentScope / 后端注册的工具实现。"
                filter={toolFilter}
                onFilterChange={setToolFilter}
                items={toolRows}
                selected={toolSel}
                onToggle={toggleTool}
                emptyText="暂无工具或未匹配筛选条件。"
              />
              <>
                <SelectableBindingBlock
                  title="平台资源（连接器）"
                  description={`先选择资源类型，再在下方勾选（当前查看「${resourceListFilterLabel(resourceKindTab)}」）。角标「已选」仅统计<strong>当前类型下</strong>的勾选；其它类型已选项在切换标签后仍保留。已勾选「文件库」类时，请切到「全部」或「文件库」标签以配置<strong>平台共享文件</strong>限定。**勾选资源的名称、描述与登记字段会在 Run 时写入系统提示词。**`}
                  toolbar={resourceKindToolbar}
                  filter={resourceFilter}
                  onFilterChange={setResourceFilter}
                  items={resourceRows}
                  selected={resourceSel}
                  selectedCountDisplay={resourceSelectedCountForTab}
                  onToggle={toggleResource}
                  emptyText="当前类型下暂无连接器，或关键字未匹配。"
                />
                {showPlatformFilesPanel ? (
                  <div className="agent-binding-section agent-platform-files-panel" aria-label="平台共享文件">
                    <div className="agent-binding-section__head">
                      <h3 className="agent-binding-section__title">
                        平台共享文件（可选限定）
                        <span className="agent-selected-count">{platformFileSel.size} 个 file_id</span>
                      </h3>
                      <p className="agent-binding-section__desc">
                        来自「可用资源配置 → 文件库」上传区。下方<strong>不勾选</strong>表示本 Agent 可读 Run 合并后的<strong>全部</strong>
                        uploaded_files；勾选后仅处理所选文件（应用私有上传仍会在合并列表中，若也要限定请只勾选需要的 ID）。
                      </p>
                    </div>
                    {libraryLoadError ? <div className="error">{libraryLoadError}</div> : null}
                    <div className="agent-platform-file-grid">
                      {libraryFiles.length === 0 ? (
                        <p className="agent-binding-empty">平台库暂无文件，请先到「平台资源」页上传。</p>
                      ) : (
                        libraryFiles.map((row) => (
                          <label
                            key={row.id}
                            className={`agent-option-tile agent-platform-file-tile ${platformFileSel.has(row.id) ? "is-selected" : ""}`}
                          >
                            <input
                              type="checkbox"
                              checked={platformFileSel.has(row.id)}
                              onChange={() => togglePlatformFile(row.id)}
                            />
                            <div className="agent-option-tile__body">
                              <span className="agent-option-tile__title">{row.original_filename}</span>
                              <span className="agent-option-tile__sub">{formatLibraryBytes(row.size_bytes)}</span>
                              <code>{row.id}</code>
                            </div>
                          </label>
                        ))
                      )}
                    </div>
                  </div>
                ) : null}
              </>
            </div>

            <details className="agent-react-details">
              <summary>模型与 ReAct 配置（JSON）</summary>
              <label className="agent-react-details__label">
                <textarea value={form.react_config} onChange={(event) => setForm({ ...form, react_config: event.target.value })} rows={12} spellCheck={false} />
              </label>
            </details>

            <label className="agent-template-editor__prompt">
              系统提示词 <span className="required-dot">*</span>
              <textarea value={form.prompt} onChange={(event) => setForm({ ...form, prompt: event.target.value })} rows={10} required placeholder="定义 Agent 的职责边界与输出风格…" />
            </label>

            <button type="submit" className="agent-template-submit">
              保存 Agent 模板
            </button>
          </form>
        </SectionCard>

        <SectionCard title="已有模板目录" description="当前磁盘上的 Agent 模板及已绑定 ID。">
          <ul className="agent-catalog-list">
            {agents.map((agent) => {
              const toolIds = agent.tool_ids ?? agent.skill_ids ?? [];
              return (
                <li key={agent.id} className="agent-catalog-row">
                  <div className="agent-catalog-row__top">
                    <span className="agent-catalog-role">{agent.role}</span>
                    <strong className="agent-catalog-name">{agent.name}</strong>
                    <code className="agent-catalog-id">{agent.id}</code>
                  </div>
                  <PillRow label="Skills" ids={agent.skill_package_ids ?? []} variant="skill" />
                  <PillRow label="工具" ids={toolIds} variant="tool" />
                  <ResourceBindingsSummary ids={agent.resource_ids ?? []} catalog={resources} />
                  {agent.platform_upload_file_ids?.length ? (
                    <div className="agent-catalog-meta agent-platform-upload-ids">
                      <strong>限定平台文件</strong>
                      <div className="agent-pill-row">
                        {agent.platform_upload_file_ids.map((fid) => (
                          <span key={fid} className="agent-pill agent-pill--resource">
                            {fid}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  <p className="agent-catalog-react muted">
                    ReAct · max_iters={(agent.react_config?.max_iters as number | undefined) ?? 6}
                  </p>
                </li>
              );
            })}
          </ul>
          {agents.length === 0 ? <p className="muted">暂无 Agent 模板。</p> : null}
        </SectionCard>
      </div>
    </>
  );
}
