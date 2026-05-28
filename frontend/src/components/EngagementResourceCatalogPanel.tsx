import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  createEngagementResourceConfig,
  deleteEngagementResourceConfig,
  listEngagementResourceConfigs,
  updateEngagementResourceConfig,
  uploadEngagementFile,
} from "../api/client";
import { SectionCard } from "./SectionCard";
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
  PLATFORM_RESOURCE_TYPE_OPTIONS,
  type PlatformResourceType,
  isKnownPlatformResourceType,
  resourceListFilterLabel,
} from "../domain/platformResourceRegistry";
import type { ResourceConfig } from "../types/domain";

type TabFilter = PlatformResourceType | "other";

export function EngagementResourceCatalogPanel({ engagementId }: { engagementId: string }) {
  const [listFilter, setListFilter] = useState<TabFilter>("web");
  const [resources, setResources] = useState<ResourceConfig[]>([]);
  const [error, setError] = useState("");
  const [ptype, setPtype] = useState<PlatformResourceType>("web");
  const [fields, setFields] = useState<Record<string, string>>(() => emptyFields("web"));
  const [form, setForm] = useState({ id: "", name: "", description: "" });
  const [formEnabled, setFormEnabled] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editUnknownType, setEditUnknownType] = useState<string | null>(null);
  const [connectionRawJson, setConnectionRawJson] = useState("{}");
  const [savingEdit, setSavingEdit] = useState(false);
  const [deletingId, setDeletingId] = useState("");
  const [filePick, setFilePick] = useState<File | null>(null);
  const [lastUploadedFilename, setLastUploadedFilename] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fieldLabels = useMemo(() => labelsFor(ptype), [ptype]);
  const filteredResources = useMemo(() => {
    if (listFilter === "other") return resources.filter((r) => !isKnownPlatformResourceType(r.type));
    return resources.filter((r) => r.type === listFilter);
  }, [resources, listFilter]);
  const showOtherTab = useMemo(() => resources.some((r) => !isKnownPlatformResourceType(r.type)), [resources]);
  const showFileLibraryPanel = listFilter === "file_store";
  const typeSelectLocked = Boolean(!editingId && listFilter !== "other" && isKnownPlatformResourceType(listFilter));
  const editingResource = editingId ? resources.find((item) => item.id === editingId) : undefined;
  const editingFileId = editingResource ? fileIdFromConfig(editingResource.connection_config ?? {}) : "";
  const editingFileName = editingResource ? fileNameFromConfig(editingResource.connection_config ?? {}) : "";
  const editingFileSize = editingResource ? formatFileStoreSize(editingResource.connection_config ?? {}) : "";

  const refresh = useCallback(async () => {
    setResources(await listEngagementResourceConfigs(engagementId));
  }, [engagementId]);

  useEffect(() => {
    refresh().catch((err: unknown) => setError(String(err)));
  }, [refresh]);

  useEffect(() => {
    if (editingId) return;
    if (listFilter !== "other" && isKnownPlatformResourceType(listFilter)) {
      setPtype(listFilter);
      setFields(emptyFields(listFilter));
      setEditUnknownType(null);
    }
  }, [listFilter, editingId]);

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
    setFilePick(null);
    setLastUploadedFilename("");
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (listFilter !== "other" && isKnownPlatformResourceType(listFilter)) {
      setPtype(listFilter);
      setFields(emptyFields(listFilter));
    } else {
      setPtype("web");
      setFields(emptyFields("web"));
    }
  }

  function beginEdit(resource: ResourceConfig) {
    setError("");
    setEditingId(resource.id);
    setFilePick(null);
    setLastUploadedFilename("");
    if (fileInputRef.current) fileInputRef.current.value = "";
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
      setConnectionRawJson(JSON.stringify(resource.connection_config ?? {}, null, 2));
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const previousFileId =
      editingResource?.type === "file_store" ? fileIdFromConfig(editingResource.connection_config ?? {}) : "";
    let originalFilename = editingResource ? fileNameFromConfig(editingResource.connection_config ?? {}) : "";

    try {
      let connection_config: Record<string, unknown>;
      let effectiveType: string;
      if (editingId && editUnknownType) {
        effectiveType = editUnknownType;
        connection_config = JSON.parse(connectionRawJson) as Record<string, unknown>;
      } else {
        effectiveType =
          typeSelectLocked && listFilter !== "other" && isKnownPlatformResourceType(listFilter) ? listFilter : ptype;
        connection_config = buildConnection(effectiveType as PlatformResourceType, fields);
      }

      const isFileStoreFlow = effectiveType === "file_store" && !editUnknownType;
      let fileId = isFileStoreFlow ? previousFileId : "";
      let uploadedSizeBytes: number | undefined;

      if (isFileStoreFlow) {
        if (filePick) {
          if (filePick.size === 0) {
            setError("文件为空（0 字节），请选择有内容的文件。");
            return;
          }
          setSavingEdit(true);
          const uploaded = await uploadEngagementFile(engagementId, filePick);
          fileId = uploaded.value;
          originalFilename = String(uploaded.metadata_json?.original_filename ?? filePick.name);
          uploadedSizeBytes =
            typeof uploaded.metadata_json?.size_bytes === "number" ? uploaded.metadata_json.size_bytes : filePick.size;
          setLastUploadedFilename(originalFilename);
          setForm((prev) => ({
            ...prev,
            name: prev.name.trim() || resourceNameFromUpload(originalFilename),
          }));
          setFilePick(null);
          if (fileInputRef.current) fileInputRef.current.value = "";
        }

        if (!editingId && !fileId) {
          setError("请选择要上传的文件。");
          return;
        }

        connection_config = buildFileStoreConnection(fields, {
          fileId,
          originalFilename,
          sizeBytes:
            uploadedSizeBytes ??
            (typeof editingResource?.connection_config?.size_bytes === "number"
              ? editingResource.connection_config.size_bytes
              : undefined),
        });
      }

      const resolvedName =
        form.name.trim() || (isFileStoreFlow ? resourceNameFromUpload(originalFilename || lastUploadedFilename) : "");
      if (!resolvedName) {
        setError(isFileStoreFlow ? "请填写名称，或留空以使用文件名。" : "请填写名称。");
        return;
      }

      if (editingId) {
        setSavingEdit(true);
        await updateEngagementResourceConfig(engagementId, editingId, {
          name: resolvedName,
          description: form.description,
          type: effectiveType,
          connection_config,
          enabled: formEnabled,
        });
        resetEditorForm();
      } else {
        setSavingEdit(true);
        await createEngagementResourceConfig(engagementId, {
          id: form.id.trim() || undefined,
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
    const linkedFileId = resource.type === "file_store" ? fileIdFromConfig(resource.connection_config ?? {}) : "";
    const linkedFileName = fileNameFromConfig(resource.connection_config ?? {});
    const ok = window.confirm(
      linkedFileId
        ? `确定删除文件资源「${resource.name}」吗？将同时删除资源登记与应用文件${linkedFileName ? `「${linkedFileName}」` : ""}（${linkedFileId}）。`
        : `确定删除「${resource.name}」（${resource.id}）吗？`,
    );
    if (!ok) return;
    setDeletingId(resource.id);
    setError("");
    try {
      await deleteEngagementResourceConfig(engagementId, resource.id);
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
      <nav className="resource-kind-tabs" aria-label="公司资源类型">
        {PLATFORM_RESOURCE_TYPE_OPTIONS.map((o) => (
          <button
            key={o.id}
            type="button"
            className={`resource-kind-tab ${listFilter === o.id ? "is-active" : ""}`}
            onClick={() => {
              setListFilter(o.id);
              if (editingId) {
                resetEditorForm();
                return;
              }
              setPtype(o.id);
              setFields(emptyFields(o.id));
              setEditUnknownType(null);
            }}
          >
            {o.label}
          </button>
        ))}
        {showOtherTab || listFilter === "other" ? (
          <button
            type="button"
            className={`resource-kind-tab ${listFilter === "other" ? "is-active" : ""}`}
            onClick={() => {
              setListFilter("other");
              if (editingId) resetEditorForm();
            }}
          >
            其他类型
          </button>
        ) : null}
      </nav>
      {error ? <div className="error">{error}</div> : null}
      <div className="grid resource-configs-layout">
        <SectionCard
          title={editingId ? "编辑公司资源" : `新增 · ${resourceListFilterLabel(listFilter)}`}
          description={
            showFileLibraryPanel
              ? "选择文件并填写说明，点击「上传并保存」即写入应用文件库与资源登记（与平台资源相同）。"
              : "公司级资源登记方式与平台资源一致；Run 时与当前 Engagement 的 Agent 绑定一并生效。"
          }
        >
          {editingId ? (
            <div className="resource-edit-banner">
              <span>
                编辑模式 · <code>{editingId}</code>
              </span>
              <button type="button" className="secondary-button" onClick={() => resetEditorForm()}>
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
                    ref={fileInputRef}
                    type="file"
                    disabled={savingEdit}
                    onChange={(e) => {
                      const picked = e.target.files?.[0] ?? null;
                      setFilePick(picked);
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
              ID（可选，留空自动生成）
              <input value={form.id} disabled={Boolean(editingId)} onChange={(e) => setForm({ ...form, id: e.target.value })} />
            </label>
            <label>
              名称
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
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
                资源类型：<strong>{resourceListFilterLabel(listFilter)}</strong>
              </p>
            ) : (
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
            )}
            <label>
              描述（面向读者的概要）
              <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </label>
            <div className="resource-enabled-card">
              <div>
                <p className="resource-enabled-card__title">资源条目状态</p>
                <p className="muted resource-enabled-card__hint">禁用后仍保留记录，但不作为可用条目对外列出。</p>
              </div>
              <button
                type="button"
                className={`resource-enabled-switch ${formEnabled ? "is-on" : ""}`}
                onClick={() => setFormEnabled((prev) => !prev)}
              >
                {formEnabled ? "已启用" : "已禁用"}
              </button>
            </div>
            {editUnknownType ? (
              <label>
                登记详情（JSON）
                <textarea
                  rows={10}
                  className="resource-json-textarea"
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
        <SectionCard title="已登记条目" description={`共 ${resources.length} 条；当前显示 ${filteredResources.length} 条。`}>
          <ul className="list resource-registry-list">
            {filteredResources.map((resource) => (
              <li key={resource.id}>
                <span className="resource-type-pill">{resource.type}</span>
                <div className="resource-registry-body">
                  <div className="resource-registry-title-row">
                    <strong>{resource.name}</strong>
                    {!resource.enabled ? <span className="resource-status-badge resource-status-badge--off">已禁用</span> : null}
                  </div>
                  <p className="muted">{resource.description || "无描述"}</p>
                  <p className="muted resource-registry-summary">登记要点：{summarizeConnection(resource)}</p>
                </div>
                <div className="resource-registry-actions">
                  <code className="resource-registry-id">{resource.id}</code>
                  <button type="button" className="secondary-button" onClick={() => beginEdit(resource)}>
                    编辑
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={deletingId === resource.id}
                    onClick={() => void handleDelete(resource)}
                  >
                    {deletingId === resource.id
                      ? "处理中…"
                      : resource.type === "file_store" && fileIdFromConfig(resource.connection_config ?? {})
                        ? "删除文件资源"
                        : "删除"}
                  </button>
                </div>
              </li>
            ))}
          </ul>
          {filteredResources.length === 0 ? <p className="muted">当前类型下暂无条目。</p> : null}
        </SectionCard>
      </div>
    </div>
  );
}
