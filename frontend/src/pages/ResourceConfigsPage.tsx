import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  createResourceConfig,
  deleteResourceConfig,
  listResourceConfigs,
  listToolConfigs,
  updateResourceConfig,
  uploadLibraryFile,
} from "../api/client";
import { SectionCard } from "../components/SectionCard";
import {
  normalizeOptionalTechnicalId,
  TECHNICAL_ID_HINT,
  TECHNICAL_ID_PLACEHOLDER,
  technicalIdValidationError,
} from "../domain/technicalId";
import {
  buildConnection,
  buildFileStoreConnection,
  emptyFields,
  fieldsFromConnection,
  fileIdFromConfig,
  fileNameFromConfig,
  formatFileStoreSize,
  labelsFor,
  resourceNameFromUpload,
  summarizeConnection,
} from "../domain/resourceCatalogForm";
import {
  type PlatformResourceType,
  PLATFORM_CONFIG_TAB_OPTIONS,
  PLATFORM_RESOURCE_TYPE_OPTIONS,
  type ResourceConfigsTabFilter,
  isKnownPlatformResourceType,
  isToolsConfigTab,
  resourceListFilterLabel,
} from "../domain/platformResourceRegistry";
import type { ResourceConfig, ToolConfig } from "../types/domain";

function initialListFilter(searchParams: URLSearchParams): ResourceConfigsTabFilter {
  return searchParams.get("tab") === "tools" ? "tools" : "web";
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

  const [libraryPick, setLibraryPick] = useState<File | null>(null);
  const [lastUploadedFilename, setLastUploadedFilename] = useState("");
  const libraryInputRef = useRef<HTMLInputElement>(null);

  const fieldLabels = useMemo(() => labelsFor(ptype), [ptype]);

  const showToolsPanel = isToolsConfigTab(listFilter);

  const filteredResources = useMemo(() => {
    if (showToolsPanel) return [];
    if (listFilter === "other") return resources.filter((r) => !isKnownPlatformResourceType(r.type));
    return resources.filter((r) => r.type === listFilter);
  }, [resources, listFilter, showToolsPanel]);

  const showOtherTab = useMemo(() => resources.some((r) => !isKnownPlatformResourceType(r.type)), [resources]);

  /** 仅当选中「文件库」类型标签时展示上传区，避免切到其他类型仍因 ptype 为 file_store 而误显文件列表 */
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
    setLibraryPick(null);
    setLastUploadedFilename("");
    if (libraryInputRef.current) libraryInputRef.current.value = "";
    if (listFilter !== "other" && isKnownPlatformResourceType(listFilter)) {
      setPtype(listFilter);
      setFields(emptyFields(listFilter));
    } else {
      setPtype("web");
      setFields(emptyFields("web"));
    }
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
    if (editingId || showToolsPanel) return;
    if (listFilter !== "other" && isKnownPlatformResourceType(listFilter)) {
      setPtype(listFilter);
      setFields(emptyFields(listFilter));
      setEditUnknownType(null);
    }
  }, [listFilter, editingId, showToolsPanel]);

  function beginEdit(resource: ResourceConfig) {
    setError("");
    setEditingId(resource.id);
    setLibraryPick(null);
    setLastUploadedFilename("");
    if (libraryInputRef.current) libraryInputRef.current.value = "";
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
    const editingResource = editingId ? resources.find((item) => item.id === editingId) : undefined;
    const previousFileId =
      editingResource?.type === "file_store" ? fileIdFromConfig(editingResource.connection_config ?? {}) : "";
    let originalFilename = editingResource ? fileNameFromConfig(editingResource.connection_config ?? {}) : "";

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
        effectiveType = typeSelectLocked && listFilter !== "other" && isKnownPlatformResourceType(listFilter) ? listFilter : ptype;
        connection_config = buildConnection(effectiveType as PlatformResourceType, fields);
      }

      const isFileStoreFlow = effectiveType === "file_store" && !editUnknownType;
      let fileId = isFileStoreFlow ? previousFileId : "";
      let uploadedSizeBytes: number | undefined;

      if (isFileStoreFlow) {
        if (libraryPick) {
          if (libraryPick.size === 0) {
            setError("文件为空（0 字节），请选择有内容的文件。");
            return;
          }
          setSavingEdit(true);
          const uploaded = await uploadLibraryFile(libraryPick);
          fileId = uploaded.id;
          originalFilename = uploaded.original_filename;
          uploadedSizeBytes = uploaded.size_bytes;
          setLastUploadedFilename(uploaded.original_filename);
          setForm((prev) => ({
            ...prev,
            name: prev.name.trim() || resourceNameFromUpload(uploaded.original_filename),
          }));
          setLibraryPick(null);
          if (libraryInputRef.current) libraryInputRef.current.value = "";
        }

        if (!editingId && !fileId) {
          setError("请选择要上传的文件。");
          return;
        }

        connection_config = {
          ...connection_config,
          ...(fileId ? { file_id: fileId } : {}),
          ...(originalFilename ? { original_filename: originalFilename } : {}),
          ...(uploadedSizeBytes != null
            ? { size_bytes: uploadedSizeBytes }
            : typeof editingResource?.connection_config?.size_bytes === "number"
              ? { size_bytes: editingResource.connection_config.size_bytes }
              : {}),
        };
      }

      const resolvedName =
        form.name.trim() || (isFileStoreFlow ? resourceNameFromUpload(originalFilename || lastUploadedFilename) : "");
      if (!resolvedName) {
        setError(isFileStoreFlow ? "请填写名称，或留空以使用文件名。" : "请填写名称。");
        return;
      }

      if (!editingId) {
        const idError = technicalIdValidationError(form.id);
        if (idError) {
          setError(idError);
          return;
        }
      }

      if (editingId) {
        setSavingEdit(true);
        await updateResourceConfig(editingId, {
          name: resolvedName,
          description: form.description,
          type: effectiveType,
          connection_config,
          enabled: formEnabled,
        });
        resetEditorForm();
      } else {
        setSavingEdit(true);
        await createResourceConfig({
          id: normalizeOptionalTechnicalId(form.id),
          name: resolvedName,
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
    const linkedFileId = resource.type === "file_store" ? fileIdFromConfig(resource.connection_config ?? {}) : "";
    const linkedFileName = fileNameFromConfig(resource.connection_config ?? {});
    const ok = window.confirm(
      isRevertBuiltin
        ? `确定移除「${resource.name}」（${resource.id}）的数据目录覆盖吗？将恢复为仓库内置版本。`
        : linkedFileId
          ? `确定删除文件资源「${resource.name}」吗？将同时删除资源登记与平台文件${linkedFileName ? `「${linkedFileName}」` : ""}（${linkedFileId}）。`
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

  const editingResource = editingId ? resources.find((item) => item.id === editingId) : undefined;
  const editingFileId = editingResource ? fileIdFromConfig(editingResource.connection_config ?? {}) : "";
  const editingFileName = editingResource ? fileNameFromConfig(editingResource.connection_config ?? {}) : "";
  const editingFileSize = editingResource ? formatFileStoreSize(editingResource.connection_config ?? {}) : "";

  return (
    <div className="page-stack">
      <header className="page-hero">
        <p className="eyebrow">Platform resources</p>
        <h1>平台资源</h1>
        <p>
          按类型浏览平台可用的<strong>连接器资源</strong>与<strong>执行工具</strong>。
          资源条目可登记说明；<strong>文件库</strong> 选择文件后一次保存即完成上传与登记；<strong>执行工具</strong> 为只读目录（
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
              : typeSelectLocked && showFileLibraryPanel
                ? `选择文件并填写说明，点击「上传并保存」即写入平台文件库与资源登记。`
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
          <form className="form resource-registry-form" onSubmit={(e) => void handleSubmit(e)}>
            {showFileLibraryPanel ? (
              <>
                <label className="resource-file-library-file-label">
                  <span>文件{editingId ? "（可选，重新选择将替换原文件）" : "（必选）"}</span>
                  <input
                    ref={libraryInputRef}
                    type="file"
                    disabled={savingEdit}
                    onChange={(e) => {
                      const picked = e.target.files?.[0] ?? null;
                      setLibraryPick(picked);
                      if (picked && !form.name.trim()) {
                        setForm((prev) => ({ ...prev, name: resourceNameFromUpload(picked.name) }));
                      }
                    }}
                  />
                </label>
                {editingId && editingFileId ? (
                  <p className="muted">
                    当前文件：{editingFileName || "—"}
                    {editingFileSize ? ` · ${editingFileSize}` : ""} · <code>{editingFileId}</code>
                  </p>
                ) : null}
              </>
            ) : null}
            <label>
              技术 ID（可选，留空自动生成）
              <input
                value={form.id}
                disabled={Boolean(editingId)}
                onChange={(event) => setForm({ ...form, id: event.target.value })}
                placeholder={TECHNICAL_ID_PLACEHOLDER}
              />
              <span className="muted" style={{ fontSize: "12px" }}>
                {TECHNICAL_ID_HINT}
              </span>
            </label>
            <label>
              名称
              <input
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                placeholder={showFileLibraryPanel ? "留空则使用文件名" : undefined}
                required={!showFileLibraryPanel}
              />
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
                {savingEdit
                  ? "保存中…"
                  : showFileLibraryPanel && !editingId
                    ? "上传并保存"
                    : editingId
                      ? "保存修改"
                      : "保存资源"}
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
                          : resource.type === "file_store" && fileIdFromConfig(resource.connection_config ?? {})
                            ? "删除文件资源"
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
