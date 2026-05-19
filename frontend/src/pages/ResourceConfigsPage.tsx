import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  createResourceConfig,
  deleteLibraryUpload,
  deleteResourceConfig,
  listLibraryUploads,
  listResourceConfigs,
  listToolConfigs,
  updateResourceConfig,
  uploadLibraryFile,
} from "../api/client";
import { SectionCard } from "../components/SectionCard";
import {
  type PlatformResourceType,
  PLATFORM_CONFIG_TAB_OPTIONS,
  PLATFORM_RESOURCE_TYPE_OPTIONS,
  type ResourceConfigsTabFilter,
  isKnownPlatformResourceType,
  isToolsConfigTab,
  resourceListFilterLabel,
} from "../domain/platformResourceRegistry";
import type { LibraryFile, ResourceConfig, ToolConfig } from "../types/domain";

function initialListFilter(searchParams: URLSearchParams): ResourceConfigsTabFilter {
  return searchParams.get("tab") === "tools" ? "tools" : "web";
}

function labelsFor(tp: PlatformResourceType): Record<string, string> {
  switch (tp) {
    case "web":
      return {
        domains: "允许域名范围（每行一条，可含通配，可选）",
        rate_limit_rpm: "速率上限参考（请求/分钟，可选）",
        notes: "合规与抓取策略说明（可选）",
      };
    case "file_store":
      return {
        notes: "文件用途或策略说明（可选）",
      };
    case "vector_store":
      return {
        index_name: "索引名（可选登记）",
        embedding_model: "Embedding 模型（可选登记）",
        vector_dim: "向量维度（可选登记）",
        notes: "命名空间 / 环境与用法补充（可选）",
      };
    case "database":
      return {
        dialect: "方言（postgres / mysql / …，可选登记）",
        secret_ref: "密钥引用 ID（勿写明文口令，可选登记）",
        schema: "默认 schema（可选）",
        notes: "权限与安全说明（可选）",
      };
    case "api":
      return {
        base_url: "Base URL（可选登记）",
        auth_type: "认证方式备注（bearer / api_key_header / none）",
        auth_header_name: "Header 名（若适用，可选）",
        notes: "环境与限流说明（可选）",
      };
    case "metrics_platform":
      return {
        provider: "系统（snowflake / databricks / custom，可选登记）",
        entity_key_field: "主体键字段（可选登记）",
        grain: "粒度（可选登记）",
        freshness_sla_hours: "数据新鲜度 SLA（小时，可选登记）",
        taxonomy_ref: "指标目录 / 数据字典链接（可选）",
        notes: "权限与脱敏说明（可选）",
      };
    default:
      return {};
  }
}

function emptyFields(tp: PlatformResourceType): Record<string, string> {
  const keys = Object.keys(labelsFor(tp));
  return Object.fromEntries(keys.map((k) => [k, ""]));
}

function fieldsFromConnection(tp: PlatformResourceType, c: Record<string, unknown>): Record<string, string> {
  const base = emptyFields(tp);
  switch (tp) {
    case "web": {
      const domains = c.allowed_domains;
      const lines = Array.isArray(domains) ? domains.map((x) => String(x)).join("\n") : "";
      return {
        ...base,
        domains: lines,
        rate_limit_rpm: c.rate_limit_rpm != null ? String(c.rate_limit_rpm) : "",
        notes: typeof c.notes === "string" ? c.notes : "",
      };
    }
    case "file_store":
      return {
        ...base,
        notes: typeof c.notes === "string" ? c.notes : "",
      };
    case "vector_store":
      return {
        ...base,
        index_name: String(c.index_name ?? ""),
        embedding_model: String(c.embedding_model ?? ""),
        vector_dim: c.vector_dim != null ? String(c.vector_dim) : "",
        notes: typeof c.notes === "string" ? c.notes : "",
      };
    case "database":
      return {
        ...base,
        dialect: String(c.dialect ?? ""),
        secret_ref: String(c.secret_ref ?? ""),
        schema: typeof c.schema === "string" ? c.schema : "",
        notes: typeof c.notes === "string" ? c.notes : "",
      };
    case "api":
      return {
        ...base,
        base_url: String(c.base_url ?? ""),
        auth_type: typeof c.auth_type === "string" ? c.auth_type : "",
        auth_header_name: typeof c.auth_header_name === "string" ? c.auth_header_name : "",
        notes: typeof c.notes === "string" ? c.notes : "",
      };
    case "metrics_platform":
      return {
        ...base,
        provider: String(c.provider ?? ""),
        entity_key_field: String(c.entity_key_field ?? ""),
        grain: String(c.grain ?? ""),
        freshness_sla_hours: c.freshness_sla_hours != null ? String(c.freshness_sla_hours) : "",
        taxonomy_ref: typeof c.taxonomy_ref === "string" ? c.taxonomy_ref : "",
        notes: typeof c.notes === "string" ? c.notes : "",
      };
    default:
      return base;
  }
}

function buildConnection(tp: PlatformResourceType, f: Record<string, string>): Record<string, unknown> {
  const trim = (s: string) => s.trim();
  switch (tp) {
    case "web": {
      const lines = (f.domains ?? "")
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean);
      const out: Record<string, unknown> = { allowed_domains: lines };
      if (trim(f.rate_limit_rpm)) {
        const n = Number(trim(f.rate_limit_rpm));
        if (!Number.isNaN(n)) out.rate_limit_rpm = n;
      }
      if (trim(f.notes)) out.notes = trim(f.notes);
      return out;
    }
    case "file_store":
      return trim(f.notes) ? { notes: trim(f.notes) } : {};
    case "vector_store":
      return {
        index_name: trim(f.index_name),
        embedding_model: trim(f.embedding_model),
        vector_dim: trim(f.vector_dim) ? Number(trim(f.vector_dim)) : undefined,
        notes: trim(f.notes) || undefined,
      };
    case "database":
      return {
        dialect: trim(f.dialect),
        secret_ref: trim(f.secret_ref),
        schema: trim(f.schema) || undefined,
        notes: trim(f.notes) || undefined,
      };
    case "api":
      return {
        base_url: trim(f.base_url),
        auth_type: trim(f.auth_type) || "none",
        auth_header_name: trim(f.auth_header_name) || undefined,
        notes: trim(f.notes) || undefined,
      };
    case "metrics_platform":
      return {
        provider: trim(f.provider),
        entity_key_field: trim(f.entity_key_field),
        grain: trim(f.grain),
        freshness_sla_hours: trim(f.freshness_sla_hours) ? Number(trim(f.freshness_sla_hours)) : undefined,
        taxonomy_ref: trim(f.taxonomy_ref) || undefined,
        notes: trim(f.notes) || undefined,
      };
    default:
      return {};
  }
}

function summarizeConnection(row: ResourceConfig): string {
  const c = row.connection_config ?? {};
  switch (row.type) {
    case "web": {
      const d = c.allowed_domains;
      if (Array.isArray(d) && d.length) return `${d.length} 个域名`;
      break;
    }
    case "vector_store":
      return [c.index_name, c.embedding_model].filter(Boolean).join(" · ") || "—";
    case "api":
      return String(c.base_url || "—");
    case "metrics_platform":
      return [c.provider, c.grain].filter(Boolean).join(" · ") || "—";
    case "file_store": {
      if (typeof c.notes === "string" && c.notes.trim()) return c.notes.trim();
      return "平台共享文件 · 用途见条目说明";
    }
    default:
      break;
  }
  try {
    const s = JSON.stringify(c);
    return s.length > 120 ? `${s.slice(0, 120)}…` : s || "—";
  } catch {
    return "—";
  }
}

function formatLibraryBytes(n: number): string {
  if (!Number.isFinite(n) || n < 0) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function ResourceConfigsPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [tools, setTools] = useState<ToolConfig[]>([]);
  const [resources, setResources] = useState<ResourceConfig[]>([]);
  const [listFilter, setListFilter] = useState<ResourceConfigsTabFilter>(() => initialListFilter(searchParams));
  const [deletingId, setDeletingId] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const [disablingId, setDisablingId] = useState("");
  const [error, setError] = useState("");
  const [form, setForm] = useState({ id: "", name: "", description: "" });
  const [formEnabled, setFormEnabled] = useState(true);
  const [ptype, setPtype] = useState<PlatformResourceType>("web");
  const [fields, setFields] = useState<Record<string, string>>(() => emptyFields("web"));
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editUnknownType, setEditUnknownType] = useState<string | null>(null);
  const [connectionRawJson, setConnectionRawJson] = useState("{}");

  const [libraryFiles, setLibraryFiles] = useState<LibraryFile[]>([]);
  const [libraryPick, setLibraryPick] = useState<File | null>(null);
  const [libraryBusy, setLibraryBusy] = useState(false);
  const [libraryBannerError, setLibraryBannerError] = useState("");
  const [libraryBannerOk, setLibraryBannerOk] = useState("");
  const [deletingLibraryId, setDeletingLibraryId] = useState("");
  const libraryInputRef = useRef<HTMLInputElement>(null);

  const fieldLabels = useMemo(() => labelsFor(ptype), [ptype]);

  const showToolsPanel = isToolsConfigTab(listFilter);

  const filteredResources = useMemo(() => {
    if (showToolsPanel) return [];
    if (listFilter === "other") return resources.filter((r) => !isKnownPlatformResourceType(r.type));
    return resources.filter((r) => r.type === listFilter);
  }, [resources, listFilter, showToolsPanel]);

  const showOtherTab = useMemo(() => resources.some((r) => !isKnownPlatformResourceType(r.type)), [resources]);

  /** 仅当选中「文件库」类型标签时展示上传区，避免切到向量库等仍因 ptype 为 file_store 而误显文件列表 */
  const showFileLibraryPanel = listFilter === "file_store";

  const typeSelectLocked =
    Boolean(!editingId && listFilter !== "other" && isKnownPlatformResourceType(listFilter));

  const changeType = useCallback((next: PlatformResourceType) => {
    setPtype(next);
    setFields(emptyFields(next));
  }, []);

  function resetEditorForm() {
    setEditingId(null);
    setEditUnknownType(null);
    setForm({ id: "", name: "", description: "" });
    setFormEnabled(true);
    setConnectionRawJson("{}");
    if (listFilter !== "other" && isKnownPlatformResourceType(listFilter)) {
      setPtype(listFilter);
      setFields(emptyFields(listFilter));
    } else {
      setPtype("web");
      setFields(emptyFields("web"));
    }
  }

  async function refreshLibraryFiles() {
    setLibraryFiles(await listLibraryUploads());
  }

  async function refresh() {
    setResources(await listResourceConfigs());
  }

  async function refreshTools() {
    setTools(await listToolConfigs());
  }

  function selectListFilter(filter: ResourceConfigsTabFilter) {
    setListFilter(filter);
    if (filter === "tools") {
      setSearchParams({ tab: "tools" });
    } else {
      setSearchParams({});
    }
    if (editingId) resetEditorForm();
  }

  useEffect(() => {
    refresh().catch((err: unknown) => setError(String(err)));
  }, []);

  useEffect(() => {
    if (!showToolsPanel) return;
    refreshTools().catch((err: unknown) => setError(String(err)));
  }, [showToolsPanel]);

  useEffect(() => {
    if (!showFileLibraryPanel) return;
    refreshLibraryFiles().catch((err: unknown) => setError(String(err)));
  }, [showFileLibraryPanel]);

  useEffect(() => {
    if (editingId || showToolsPanel) return;
    if (listFilter !== "other" && isKnownPlatformResourceType(listFilter)) {
      setPtype(listFilter);
      setFields(emptyFields(listFilter));
      setEditUnknownType(null);
    }
  }, [listFilter, editingId, showToolsPanel]);

  async function handleLibraryUpload() {
    if (!libraryPick) return;
    setLibraryBannerError("");
    setLibraryBannerOk("");
    setLibraryBusy(true);
    try {
      const row = await uploadLibraryFile(libraryPick);
      setLibraryBannerOk(`已上传「${libraryPick.name}」→ ${row.id}（可在应用 Run 的资源合并中使用该 file_id）。`);
      setLibraryPick(null);
      if (libraryInputRef.current) libraryInputRef.current.value = "";
      await refreshLibraryFiles();
    } catch (err: unknown) {
      setLibraryBannerError(String(err));
    } finally {
      setLibraryBusy(false);
    }
  }

  async function handleDeleteLibraryRow(row: LibraryFile) {
    const ok = window.confirm(`确定从平台文件库删除「${row.original_filename}」（${row.id}）吗？删除后合并资源时将不再包含该文件。`);
    if (!ok) return;
    setLibraryBannerError("");
    setLibraryBannerOk("");
    setDeletingLibraryId(row.id);
    try {
      await deleteLibraryUpload(row.id);
      setLibraryBannerOk(`已删除 ${row.id}`);
      await refreshLibraryFiles();
    } catch (err: unknown) {
      setLibraryBannerError(String(err));
    } finally {
      setDeletingLibraryId("");
    }
  }

  function beginEdit(resource: ResourceConfig) {
    setError("");
    setEditingId(resource.id);
    if (isKnownPlatformResourceType(resource.type)) {
      setListFilter(resource.type);
    } else {
      setListFilter("other");
    }
    setForm({ id: resource.id, name: resource.name, description: resource.description });
    setFormEnabled(resource.enabled);
    if (isKnownPlatformResourceType(resource.type)) {
      setEditUnknownType(null);
      setPtype(resource.type);
      setFields(fieldsFromConnection(resource.type, resource.connection_config ?? {}));
    } else {
      setEditUnknownType(resource.type);
      setPtype("web");
      setFields(emptyFields("web"));
      try {
        setConnectionRawJson(JSON.stringify(resource.connection_config ?? {}, null, 2));
      } catch {
        setConnectionRawJson("{}");
      }
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleDisableBuiltin(resource: ResourceConfig) {
    const ok = window.confirm(`确定禁用内置资源条目「${resource.name}」（${resource.id}）吗？将在数据目录写入覆盖文件，可随时删除覆盖恢复默认。`);
    if (!ok) return;
    setError("");
    setDisablingId(resource.id);
    try {
      await updateResourceConfig(resource.id, { enabled: false });
      await refresh();
    } catch (err: unknown) {
      setError(String(err));
    } finally {
      setDisablingId("");
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      let connection_config: Record<string, unknown>;
      let effectiveType: string;
      if (editingId && editUnknownType) {
        effectiveType = editUnknownType;
        try {
          connection_config = JSON.parse(connectionRawJson) as Record<string, unknown>;
          if (typeof connection_config !== "object" || connection_config === null || Array.isArray(connection_config)) {
            throw new Error("connection_config 必须是 JSON 对象");
          }
        } catch (e: unknown) {
          throw new Error(e instanceof Error ? e.message : "connection_config JSON 无效");
        }
      } else {
        effectiveType = ptype;
        connection_config = buildConnection(ptype, fields);
      }

      if (editingId) {
        setSavingEdit(true);
        await updateResourceConfig(editingId, {
          name: form.name,
          description: form.description,
          type: effectiveType,
          connection_config,
          enabled: formEnabled,
        });
        resetEditorForm();
      } else {
        await createResourceConfig({
          id: (form.id || "").trim() || undefined,
          name: form.name,
          type: effectiveType,
          description: form.description,
          connection_config,
          enabled: formEnabled,
        });
        resetEditorForm();
      }
      await refresh();
    } catch (err: unknown) {
      setError(String(err));
    } finally {
      setSavingEdit(false);
    }
  }

  async function handleDelete(resource: ResourceConfig) {
    if (!resource.deletable) return;
    const isRevertBuiltin = Boolean(resource.builtin_base);
    const ok = window.confirm(
      isRevertBuiltin
        ? `确定移除「${resource.name}」（${resource.id}）的数据目录覆盖吗？将恢复为仓库内置版本。`
        : `确定删除「${resource.name}」（${resource.id}）吗？该资源条目将从平台移除且不可恢复。`,
    );
    if (!ok) return;
    setError("");
    setDeletingId(resource.id);
    try {
      await deleteResourceConfig(resource.id);
      if (editingId === resource.id) resetEditorForm();
      await refresh();
    } catch (err: unknown) {
      setError(String(err));
    } finally {
      setDeletingId("");
    }
  }

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Platform resources</p>
        <h1>平台资源</h1>
        <p>
          按类型浏览平台可用的<strong>连接器资源</strong>与<strong>执行工具</strong>。
          资源条目可登记说明；<strong>文件库</strong> 支持上传共享文件；<strong>执行工具</strong> 为只读目录（
          <code>tools.yaml</code>），在「场景与 Agent」中通过 <code>tool_ids</code> 引用。
        </p>
        <nav className="resource-kind-tabs" aria-label="平台资源类型">
          {PLATFORM_CONFIG_TAB_OPTIONS.map((o) => (
            <button
              key={o.id}
              type="button"
              className={`resource-kind-tab ${listFilter === o.id ? "is-active" : ""}`}
              aria-current={listFilter === o.id ? "true" : undefined}
              onClick={() => selectListFilter(o.id)}
            >
              {o.label}
            </button>
          ))}
          {showOtherTab || listFilter === "other" ? (
            <button
              type="button"
              className={`resource-kind-tab ${listFilter === "other" ? "is-active" : ""}`}
              aria-current={listFilter === "other" ? "true" : undefined}
              onClick={() => selectListFilter("other")}
            >
              其他类型
            </button>
          ) : null}
        </nav>
      </header>
      {error ? <div className="error">{error}</div> : null}
      {showToolsPanel ? (
        <SectionCard
          title="平台工具目录"
          description={`共 ${tools.length} 个；仅展示，修改请编辑 tools.yaml 或通过运维流程发布。`}
        >
          <ul className="list platform-tools-list">
            {tools.map((tool) => (
              <li key={tool.id}>
                <div className="platform-tool-row">
                  <span className={`status ${tool.enabled ? "published" : "draft"}`}>
                    {tool.enabled ? "enabled" : "disabled"}
                  </span>
                  <div className="platform-tool-row__main">
                    <strong>{tool.name}</strong>
                    <code className="platform-tool-row__id">{tool.id}</code>
                    <p className="muted">{tool.description || "无描述"}</p>
                    <small className="muted platform-tool-row__impl">{tool.implementation}</small>
                    {tool.requires_api_key ? <span className="resource-status-badge">需 API Key</span> : null}
                  </div>
                </div>
              </li>
            ))}
          </ul>
          {tools.length === 0 ? <p className="muted">暂无工具配置。</p> : null}
        </SectionCard>
      ) : (
      <div className="grid resource-configs-layout">
        <SectionCard
          title={
            editingId
              ? "编辑资源条目"
              : listFilter !== "other"
                ? `新增 · ${resourceListFilterLabel(listFilter)}`
                : "新增资源条目"
          }
          description={
            editingId
              ? `正在编辑 ${editingId}。保存写入数据目录（内置 ID 会产生覆盖文件）。`
              : typeSelectLocked
                ? `当前类型为「${resourceListFilterLabel(listFilter)}」。保存后加入右侧该类型的已登记列表。`
                : "选择类型后填写名称与说明；登记字段均可选填，用于记录资源概况。内置同名 ID 若已存在会因冲突被拒绝。"
          }
        >
          {editingId ? (
            <div className="resource-edit-banner">
              <span>
                编辑模式 · <code>{editingId}</code>
              </span>
              <button type="button" className="ghost-button" onClick={() => resetEditorForm()}>
                取消编辑
              </button>
            </div>
          ) : null}
          {showFileLibraryPanel ? (
            <div className="resource-file-library-panel">
              <p className="resource-file-library-panel__title">平台共享文件</p>
              <p className="muted resource-file-library-panel__hint">
                文件保存在 <code>DD_DATA_ROOT/platform/uploads</code>
                。在此处<strong>上传 / 删除</strong>
                即可维护文件本体；下方表单用于登记一条「文件库」类资源的<strong>名称与用途说明</strong>
                （可选，与工具无关）。
              </p>
              {libraryBannerError ? <div className="error">{libraryBannerError}</div> : null}
              {libraryBannerOk ? <p className="resource-file-library-panel__ok">{libraryBannerOk}</p> : null}
              <div className="inline-form resource-file-library-upload-row">
                <label className="resource-file-library-file-label">
                  <span className="muted resource-file-library-file-caption">文件</span>
                  <input
                    ref={libraryInputRef}
                    type="file"
                    disabled={libraryBusy}
                    onChange={(e) => setLibraryPick(e.target.files?.[0] ?? null)}
                  />
                </label>
                <button type="button" disabled={libraryBusy || !libraryPick} onClick={() => void handleLibraryUpload()}>
                  {libraryBusy ? "上传中…" : "上传到平台库"}
                </button>
              </div>
              {libraryFiles.length ? (
                <ul className="resource-library-file-list">
                  {libraryFiles.map((row) => (
                    <li key={row.id} className="resource-library-file-row">
                      <div>
                        <strong>{row.original_filename}</strong>
                        <span className="muted resource-library-file-meta">{formatLibraryBytes(row.size_bytes)}</span>
                        <div>
                          <code className="resource-library-file-id">{row.id}</code>
                        </div>
                      </div>
                      <button
                        type="button"
                        className="secondary-button"
                        disabled={deletingLibraryId === row.id || libraryBusy}
                        onClick={() => void handleDeleteLibraryRow(row)}
                      >
                        {deletingLibraryId === row.id ? "删除中…" : "删除"}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted resource-library-empty">暂无平台文件。</p>
              )}
            </div>
          ) : null}
          <form className="form resource-registry-form" onSubmit={(e) => void handleSubmit(e)}>
            <label>
              ID（可选，留空自动生成）
              <input
                value={form.id}
                disabled={Boolean(editingId)}
                onChange={(event) => setForm({ ...form, id: event.target.value })}
              />
            </label>
            <label>
              名称
              <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
            </label>
            {editUnknownType ? (
              <p className="resource-unknown-type-note">
                类型 <code>{editUnknownType}</code>（非预设）；详情请以下方 JSON 登记。
              </p>
            ) : typeSelectLocked ? (
              <p className="resource-type-locked-note">
                资源类型：<strong>{PLATFORM_RESOURCE_TYPE_OPTIONS.find((t) => t.id === ptype)?.label ?? ptype}</strong>
                <span className="muted" style={{ display: "block", marginTop: "6px", fontSize: "13px" }}>
                  {PLATFORM_RESOURCE_TYPE_OPTIONS.find((t) => t.id === ptype)?.hint}
                </span>
              </p>
            ) : (
              <>
                <label>
                  类型
                  <select value={ptype} onChange={(e) => changeType(e.target.value as PlatformResourceType)}>
                    {PLATFORM_RESOURCE_TYPE_OPTIONS.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                <p className="muted resource-type-hint">{PLATFORM_RESOURCE_TYPE_OPTIONS.find((t) => t.id === ptype)?.hint}</p>
              </>
            )}
            <label>
              描述（面向读者的概要）
              <input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
            </label>
            <div className="resource-enabled-card">
              <div>
                <p className="resource-enabled-card__title">资源条目状态</p>
                <p className="muted resource-enabled-card__hint">
                  禁用后仍保留记录，但不作为可用条目对外列出。
                </p>
              </div>
              <button
                type="button"
                className={`resource-enabled-switch ${formEnabled ? "is-on" : ""}`}
                aria-pressed={formEnabled}
                onClick={() => setFormEnabled((prev) => !prev)}
              >
                {formEnabled ? "已启用" : "已禁用"}
              </button>
            </div>
            {editUnknownType ? (
              <label>
                登记详情（JSON）
                <textarea
                  rows={14}
                  className="resource-json-textarea"
                  spellCheck={false}
                  value={connectionRawJson}
                  onChange={(e) => setConnectionRawJson(e.target.value)}
                />
              </label>
            ) : (
              <div className="resource-registry-fields">
                {Object.entries(fieldLabels).map(([key, label]) => (
                  <label key={key}>
                    {label}
                    {key === "domains" || key === "notes" ? (
                      <textarea
                        rows={key === "domains" ? 3 : 2}
                        value={fields[key] ?? ""}
                        onChange={(e) => setFields({ ...fields, [key]: e.target.value })}
                      />
                    ) : (
                      <input value={fields[key] ?? ""} onChange={(e) => setFields({ ...fields, [key]: e.target.value })} />
                    )}
                  </label>
                ))}
              </div>
            )}
            <div className="resource-form-actions">
              <button type="submit" disabled={savingEdit}>
                {savingEdit ? "保存中…" : editingId ? "保存修改" : "保存资源"}
              </button>
              {editingId ? (
                <button type="button" className="secondary-button" onClick={() => resetEditorForm()}>
                  取消
                </button>
              ) : null}
            </div>
          </form>
        </SectionCard>
        <SectionCard
          title="已登记条目"
          description={`共 ${resources.length} 条；当前类型「${resourceListFilterLabel(listFilter)}」显示 ${filteredResources.length} 条。可编辑、禁用或删除（内置条目见按钮说明）。`}
        >
          <ul className="list resource-registry-list">
            {filteredResources.map((resource) => (
              <li key={resource.id}>
                <span className="resource-type-pill">{resource.type}</span>
                <div className="resource-registry-body">
                  <div className="resource-registry-title-row">
                    <strong>{resource.name}</strong>
                    {!resource.enabled ? <span className="resource-status-badge resource-status-badge--off">已禁用</span> : null}
                    {resource.builtin_base ? (
                      <span className="resource-status-badge resource-status-badge--builtin">内置</span>
                    ) : null}
                  </div>
                  <p className="muted">{resource.description || "无描述"}</p>
                  <p className="muted resource-registry-summary">登记要点：{summarizeConnection(resource)}</p>
                </div>
                <div className="resource-registry-actions">
                  <code className="resource-registry-id">{resource.id}</code>
                  <button type="button" className="secondary-button" onClick={() => beginEdit(resource)}>
                    编辑
                  </button>
                  {!resource.deletable && resource.builtin_base && resource.enabled ? (
                    <button
                      type="button"
                      className="secondary-button"
                      disabled={disablingId === resource.id}
                      onClick={() => void handleDisableBuiltin(resource)}
                    >
                      {disablingId === resource.id ? "处理中…" : "禁用"}
                    </button>
                  ) : null}
                  {resource.deletable ? (
                    <button
                      type="button"
                      className="secondary-button"
                      disabled={deletingId === resource.id}
                      onClick={() => void handleDelete(resource)}
                    >
                      {deletingId === resource.id
                        ? "处理中…"
                        : resource.builtin_base
                          ? "移除覆盖"
                          : "删除"}
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
          {filteredResources.length === 0 ? (
            <p className="muted resource-registry-empty-filter">当前类型下暂无已登记条目。</p>
          ) : null}
        </SectionCard>
      </div>
      )}
    </div>
  );
}
