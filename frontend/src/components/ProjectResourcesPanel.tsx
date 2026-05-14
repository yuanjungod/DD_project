import { FormEvent, useCallback, useMemo, useState } from "react";

import { createResource, deleteResource, uploadProjectFile } from "../api/client";
import {
  PROJECT_RESOURCE_TYPE_LABELS,
  type ParsedProjectResource,
  type ProjectResourceType,
  emptyFieldsForResourceType,
  headlineForResourceRow,
  parseProjectResourceForm,
} from "../domain/projectResources";
import type { Resource } from "../types/domain";

export type { ProjectResourceType } from "../domain/projectResources";
export { PROJECT_RESOURCE_TYPE_LABELS } from "../domain/projectResources";

export type DraftResourceRow = ParsedProjectResource & { tempId: string };

type PersistedProps = {
  variant?: "persisted";
  projectId: string;
  resources: Resource[];
  onRefresh: () => Promise<void> | void;
};

type DraftProps = {
  variant: "draft";
  draftRows: DraftResourceRow[];
  onDraftRowsChange: (rows: DraftResourceRow[]) => void;
  disabled?: boolean;
};

export type ProjectResourcesPanelProps = PersistedProps | DraftProps;

export function ProjectResourcesPanel(props: ProjectResourcesPanelProps) {
  const isDraft = props.variant === "draft";
  const [rtype, setRtype] = useState<ProjectResourceType>("trusted_source");
  const [fields, setFields] = useState<Record<string, string>>(() => emptyFieldsForResourceType("trusted_source"));
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState("");
  const [uploadPick, setUploadPick] = useState<File | null>(null);

  const listRows = useMemo(() => {
    if (props.variant === "draft") return props.draftRows;
    return [...props.resources].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, [props]);

  const changeType = useCallback((next: ProjectResourceType) => {
    setRtype(next);
    setFields(emptyFieldsForResourceType(next));
    setLocalError("");
  }, []);

  const formDisabled = isDraft ? Boolean(props.disabled) : busy;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError("");
    if (isDraft ? props.disabled : false) return;

    const parsed = parseProjectResourceForm(rtype, fields);
    if (!parsed) {
      setLocalError("请填写必填主字段后再添加。");
      return;
    }

    if (isDraft) {
      const row: DraftResourceRow = {
        tempId:
          typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `t_${Date.now()}_${Math.random()}`,
        ...parsed,
      };
      props.onDraftRowsChange([row, ...props.draftRows]);
      setFields(emptyFieldsForResourceType(rtype));
      return;
    }

    setBusy(true);
    try {
      await createResource(props.projectId, parsed);
      setFields(emptyFieldsForResourceType(rtype));
      await props.onRefresh();
    } catch (err: unknown) {
      setLocalError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleDeletePersisted(id: string) {
    if (isDraft) return;
    setLocalError("");
    setBusy(true);
    try {
      await deleteResource(props.projectId, id);
      await props.onRefresh();
    } catch (err: unknown) {
      setLocalError(String(err));
    } finally {
      setBusy(false);
    }
  }

  function handleDeleteDraft(tempId: string) {
    if (!isDraft) return;
    props.onDraftRowsChange(props.draftRows.filter((r) => r.tempId !== tempId));
  }

  async function handleUploadSelected() {
    if (props.variant === "draft" || !uploadPick) return;
    const projectId = props.projectId;
    setLocalError("");
    setBusy(true);
    try {
      await uploadProjectFile(projectId, uploadPick);
      setUploadPick(null);
      await props.onRefresh();
    } catch (err: unknown) {
      setLocalError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="project-resources-panel">
      {localError ? <div className="error" style={{ marginBottom: "0.75rem" }}>{localError}</div> : null}
      {!isDraft ? (
        <div style={{ marginBottom: "1rem", paddingBottom: "1rem", borderBottom: "1px solid var(--border-subtle, #e5e7eb)" }}>
          <p className="muted" style={{ fontSize: "13px", marginBottom: "10px" }}>
            <strong>应用专属文件库</strong>：PDF / Office 等保存在本应用目录；另有<strong>平台共享文件库</strong>（可用资源配置 →
            文件库），其中文件会在<strong>任意应用</strong>
            的 Run 中自动并入 <code>resources.uploaded_files</code>（需工作流绑定「上传文件库」）。
          </p>
          <div className="inline-form" style={{ flexWrap: "wrap", alignItems: "center", gap: "10px" }}>
            <label style={{ margin: 0, flex: "1 1 200px" }}>
              <span className="muted" style={{ fontSize: "12px", display: "block", marginBottom: "4px" }}>
                选择文件
              </span>
              <input
                type="file"
                disabled={busy}
                onChange={(e) => setUploadPick(e.target.files?.[0] ?? null)}
              />
            </label>
            <button type="button" disabled={busy || !uploadPick} onClick={() => void handleUploadSelected()}>
              {busy ? "上传中…" : "上传到文件库"}
            </button>
          </div>
        </div>
      ) : null}
      <form className="form project-resources-form" onSubmit={(e) => void handleSubmit(e)}>
        <label>
          资源类型
          <select value={rtype} onChange={(e) => changeType(e.target.value as ProjectResourceType)} disabled={formDisabled}>
            {(Object.keys(PROJECT_RESOURCE_TYPE_LABELS) as ProjectResourceType[]).map((k) => (
              <option key={k} value={k}>
                {PROJECT_RESOURCE_TYPE_LABELS[k]}
              </option>
            ))}
          </select>
        </label>
        <p className="muted" style={{ margin: "-4px 0 4px", fontSize: "13px" }}>
          {rtype === "trusted_source" && "用于补充可信网址、研报链接或简短说明（写入主字段，可附显示名）。"}
          {rtype === "blocked_source" && "域名、URL 片段或站点名；Agent 采集时应降低权重或忽略。"}
          {rtype === "competitor" && "对标企业名称必填；官网/股票代码写进附属字段便于消歧。"}
          {rtype === "file_reference" && "可直接使用上方文件上传；如需对接外部托管 ID，也可手动填写 file_id。"}
          {rtype === "external_clue" && "会议纪、路演、熟人渠道等不可用 URL 表达的线索。"}
          {rtype === "metric" &&
            "定义尽调时要盯的 KPI：代码 + 中文名 + 单位 + 口径说明 + 数据来源；可设比较方向与阈值。"}
          {rtype === "agent_resource_scope" && "按本应用的 Agent ID 限定可见文件。留空文件列表时仅作为备注，不会收窄 file_reader。"}
        </p>

        {rtype === "trusted_source" ? (
          <>
            <label>
              URL 或文本
              <input
                value={fields.value ?? ""}
                onChange={(e) => setFields({ ...fields, value: e.target.value })}
                placeholder="https://..."
                disabled={formDisabled}
              />
            </label>
            <label>
              显示名（可选）
              <input
                value={fields.label ?? ""}
                onChange={(e) => setFields({ ...fields, label: e.target.value })}
                disabled={formDisabled}
              />
            </label>
            <label>
              备注
              <input
                value={fields.notes ?? ""}
                onChange={(e) => setFields({ ...fields, notes: e.target.value })}
                disabled={formDisabled}
              />
            </label>
          </>
        ) : null}

        {rtype === "blocked_source" ? (
          <>
            <label>
              屏蔽对象
              <input
                value={fields.value ?? ""}
                onChange={(e) => setFields({ ...fields, value: e.target.value })}
                placeholder="域名、URL 或关键词"
                disabled={formDisabled}
              />
            </label>
            <label>
              备注
              <input
                value={fields.notes ?? ""}
                onChange={(e) => setFields({ ...fields, notes: e.target.value })}
                disabled={formDisabled}
              />
            </label>
          </>
        ) : null}

        {rtype === "competitor" ? (
          <>
            <label>
              企业名称
              <input
                value={fields.value ?? ""}
                onChange={(e) => setFields({ ...fields, value: e.target.value })}
                disabled={formDisabled}
              />
            </label>
            <label>
              官网（可选）
              <input
                value={fields.website ?? ""}
                onChange={(e) => setFields({ ...fields, website: e.target.value })}
                disabled={formDisabled}
              />
            </label>
            <label>
              股票代码 / 简称（可选）
              <input
                value={fields.ticker ?? ""}
                onChange={(e) => setFields({ ...fields, ticker: e.target.value })}
                disabled={formDisabled}
              />
            </label>
            <label>
              备注
              <input
                value={fields.notes ?? ""}
                onChange={(e) => setFields({ ...fields, notes: e.target.value })}
                disabled={formDisabled}
              />
            </label>
          </>
        ) : null}

        {rtype === "file_reference" ? (
          <>
            <label>
              file_id
              <input
                value={fields.value ?? ""}
                onChange={(e) => setFields({ ...fields, value: e.target.value })}
                placeholder="file_xxx"
                disabled={formDisabled}
              />
            </label>
            <label>
              标签（可选）
              <input
                value={fields.label ?? ""}
                onChange={(e) => setFields({ ...fields, label: e.target.value })}
                disabled={formDisabled}
              />
            </label>
            <label>
              备注
              <input
                value={fields.notes ?? ""}
                onChange={(e) => setFields({ ...fields, notes: e.target.value })}
                disabled={formDisabled}
              />
            </label>
          </>
        ) : null}

        {rtype === "external_clue" ? (
          <>
            <label>
              线索摘要
              <textarea
                rows={3}
                value={fields.summary ?? ""}
                onChange={(e) => setFields({ ...fields, summary: e.target.value })}
                disabled={formDisabled}
              />
            </label>
            <label>
              类别（可选）
              <input
                value={fields.category ?? ""}
                onChange={(e) => setFields({ ...fields, category: e.target.value })}
                placeholder="例如：渠道、供应链、政策"
                disabled={formDisabled}
              />
            </label>
            <label>
              优先级
              <select
                value={fields.priority ?? "normal"}
                onChange={(e) => setFields({ ...fields, priority: e.target.value })}
                disabled={formDisabled}
              >
                <option value="low">低</option>
                <option value="normal">普通</option>
                <option value="high">高</option>
              </select>
            </label>
            <label>
              来源标签（可选）
              <input
                value={fields.source_label ?? ""}
                onChange={(e) => setFields({ ...fields, source_label: e.target.value })}
                disabled={formDisabled}
              />
            </label>
            <label>
              备注
              <input
                value={fields.notes ?? ""}
                onChange={(e) => setFields({ ...fields, notes: e.target.value })}
                disabled={formDisabled}
              />
            </label>
          </>
        ) : null}

        {rtype === "metric" ? (
          <>
            <div className="grid two" style={{ gap: "12px" }}>
              <label>
                指标代码（唯一键）
                <input
                  value={fields.code ?? ""}
                  onChange={(e) => setFields({ ...fields, code: e.target.value })}
                  placeholder="gross_margin_ttm"
                  disabled={formDisabled}
                />
              </label>
              <label>
                显示名称
                <input
                  value={fields.name ?? ""}
                  onChange={(e) => setFields({ ...fields, name: e.target.value })}
                  placeholder="毛利率（TTM）"
                  disabled={formDisabled}
                />
              </label>
            </div>
            <label>
              单位
              <input
                value={fields.unit ?? ""}
                onChange={(e) => setFields({ ...fields, unit: e.target.value })}
                placeholder="% 、 CN¥ 亿 、 天数"
                disabled={formDisabled}
              />
            </label>
            <label>
              口径 / 说明
              <textarea
                rows={2}
                value={fields.description ?? ""}
                onChange={(e) => setFields({ ...fields, description: e.target.value })}
                disabled={formDisabled}
              />
            </label>
            <div className="grid two" style={{ gap: "12px" }}>
              <label>
                指标分类
                <select
                  value={fields.category ?? "general"}
                  onChange={(e) => setFields({ ...fields, category: e.target.value })}
                  disabled={formDisabled}
                >
                  <option value="general">通用</option>
                  <option value="profitability">盈利能力</option>
                  <option value="liquidity">偿债与流动性</option>
                  <option value="growth">成长</option>
                  <option value="risk">风险</option>
                  <option value="esg">ESG</option>
                </select>
              </label>
              <label>
                数据来源类型
                <select
                  value={fields.source_type ?? "manual"}
                  onChange={(e) => setFields({ ...fields, source_type: e.target.value })}
                  disabled={formDisabled}
                >
                  <option value="manual">手工录入 / 访谈</option>
                  <option value="management_report">管理层报告</option>
                  <option value="regulatory_filing">监管披露</option>
                  <option value="api">内部数仓 / API</option>
                  <option value="calculated">由其他指标派生</option>
                </select>
              </label>
            </div>
            <label>
              数据定位（报表科目、API 字段、章节号）
              <input
                value={fields.source_ref ?? ""}
                onChange={(e) => setFields({ ...fields, source_ref: e.target.value })}
                disabled={formDisabled}
              />
            </label>
            <label>
              比较方向
              <select
                value={fields.target_direction ?? "unspecified"}
                onChange={(e) => setFields({ ...fields, target_direction: e.target.value })}
                disabled={formDisabled}
              >
                <option value="unspecified">不指定</option>
                <option value="higher_is_better">越高越好</option>
                <option value="lower_is_better">越低越好</option>
                <option value="in_range">落在区间</option>
              </select>
            </label>
            <div className="grid two" style={{ gap: "12px" }}>
              <label>
                阈值运算符（可选）
                <select
                  value={fields.threshold_op ?? ""}
                  onChange={(e) => setFields({ ...fields, threshold_op: e.target.value })}
                  disabled={formDisabled}
                >
                  <option value="">无</option>
                  <option value=">">大于</option>
                  <option value=">=">大于等于</option>
                  <option value="<">小于</option>
                  <option value="<=">小于等于</option>
                  <option value="==">等于</option>
                </select>
              </label>
              <label>
                阈值（可选）
                <input
                  value={fields.threshold_value ?? ""}
                  onChange={(e) => setFields({ ...fields, threshold_value: e.target.value })}
                  placeholder="例如 20 或 0.2"
                  disabled={formDisabled}
                />
              </label>
            </div>
            <div className="grid two" style={{ gap: "12px" }}>
              <label>
                更新频率（可选）
                <input
                  value={fields.frequency ?? ""}
                  onChange={(e) => setFields({ ...fields, frequency: e.target.value })}
                  placeholder="季度 / 年度"
                  disabled={formDisabled}
                />
              </label>
              <label>
                基线值（可选）
                <input
                  value={fields.baseline_value ?? ""}
                  onChange={(e) => setFields({ ...fields, baseline_value: e.target.value })}
                  disabled={formDisabled}
                />
              </label>
            </div>
            <label>
              备注
              <input
                value={fields.notes ?? ""}
                onChange={(e) => setFields({ ...fields, notes: e.target.value })}
                disabled={formDisabled}
              />
            </label>
          </>
        ) : null}

        {rtype === "agent_resource_scope" ? (
          <>
            <label>
              Agent ID
              <input
                value={fields.agent_id ?? ""}
                onChange={(e) => setFields({ ...fields, agent_id: e.target.value })}
                placeholder="例如 CompanyProfileAgent 或 agent_tpl_xxx"
                disabled={formDisabled}
              />
            </label>
            <label>
              可见 file_id（逗号或换行分隔）
              <textarea
                rows={3}
                value={fields.uploaded_file_ids ?? ""}
                onChange={(e) => setFields({ ...fields, uploaded_file_ids: e.target.value })}
                placeholder="file_xxx&#10;file_yyy"
                disabled={formDisabled}
              />
            </label>
            <label>
              备注
              <input
                value={fields.notes ?? ""}
                onChange={(e) => setFields({ ...fields, notes: e.target.value })}
                disabled={formDisabled}
              />
            </label>
          </>
        ) : null}

        <button type="submit" disabled={formDisabled}>
          {!isDraft && busy ? "提交中…" : isDraft ? "加入列表" : "添加到应用资源"}
        </button>
      </form>

      <ul className="list resource-library-list">
        {listRows.map((row) => (
          <li key={isDraft ? (row as DraftResourceRow).tempId : (row as Resource).id}>
            <span className="resource-type-pill">{row.type}</span>
            <strong>{headlineForResourceRow(row)}</strong>
            <button
              type="button"
              className="ghost-button resource-delete-btn"
              onClick={() =>
                isDraft
                  ? handleDeleteDraft((row as DraftResourceRow).tempId)
                  : void handleDeletePersisted((row as Resource).id)
              }
              disabled={formDisabled}
            >
              删除
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
