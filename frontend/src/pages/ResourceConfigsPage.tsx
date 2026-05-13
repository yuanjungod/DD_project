import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { createResourceConfig, listResourceConfigs } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import type { ResourceConfig } from "../types/domain";

type PlatformResourceType =
  | "web"
  | "file_store"
  | "vector_store"
  | "database"
  | "api"
  | "metrics_platform";

const TYPE_OPTIONS: { id: PlatformResourceType; label: string; hint: string }[] = [
  { id: "web", label: "公开网页", hint: "允许抓取的域名、robots 相关说明。" },
  { id: "file_store", label: "文件库", hint: "对象存储路径或挂载根目录。" },
  { id: "vector_store", label: "向量库", hint: "索引名、embedding 模型与维度。" },
  { id: "database", label: "业务数据库", hint: "连接方式走密钥引用，不写明文口令。" },
  { id: "api", label: "外部 API", hint: "Base URL + 认证方式占位。" },
  {
    id: "metrics_platform",
    label: "指标 / 数仓平台",
    hint: "对齐内部指标口径：实体字段、粒度、刷新 SLA。",
  },
];

function labelsFor(tp: PlatformResourceType): Record<string, string> {
  switch (tp) {
    case "web":
      return {
        domains: "允许域名（每行一个，可含通配）",
        rate_limit_rpm: "速率上限（请求/分钟，可选）",
        notes: "合规 / robots 说明",
      };
    case "file_store":
      return {
        bucket_or_root: "Bucket 或根路径",
        region: "区域（可选）",
        path_prefix: "路径前缀（可选）",
        notes: "访问方式（只读凭证名等）",
      };
    case "vector_store":
      return {
        index_name: "索引名",
        embedding_model: "Embedding 模型",
        vector_dim: "向量维度",
        notes: "命名空间 / 过滤字段",
      };
    case "database":
      return {
        dialect: "方言（postgres / mysql / …）",
        secret_ref: "连接串或 DSN 的密钥引用 ID",
        schema: "默认 schema（可选）",
        notes: "只读账号、行级安全说明",
      };
    case "api":
      return {
        base_url: "Base URL",
        auth_type: "认证（bearer / api_key_header / none）",
        auth_header_name: "Header 名（若 api_key_header）",
        notes: "限流、环境（prod/stage）",
      };
    case "metrics_platform":
      return {
        provider: "系统（snowflake / databricks / custom）",
        entity_key_field: "主体键字段（如 company_id）",
        grain: "粒度（日 / 季 / 报告期）",
        freshness_sla_hours: "数据新鲜度 SLA（小时）",
        taxonomy_ref: "指标目录 / 数据字典链接",
        notes: "行级权限、脱敏策略",
      };
    default:
      return {};
  }
}

function emptyFields(tp: PlatformResourceType): Record<string, string> {
  const keys = Object.keys(labelsFor(tp));
  return Object.fromEntries(keys.map((k) => [k, ""]));
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
      return {
        bucket_or_root: trim(f.bucket_or_root),
        region: trim(f.region) || undefined,
        path_prefix: trim(f.path_prefix) || undefined,
        notes: trim(f.notes) || undefined,
      };
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

export function ResourceConfigsPage() {
  const [resources, setResources] = useState<ResourceConfig[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ id: "", name: "", description: "" });
  const [ptype, setPtype] = useState<PlatformResourceType>("web");
  const [fields, setFields] = useState<Record<string, string>>(() => emptyFields("web"));

  const fieldLabels = useMemo(() => labelsFor(ptype), [ptype]);

  const changeType = useCallback((next: PlatformResourceType) => {
    setPtype(next);
    setFields(emptyFields(next));
  }, []);

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
      const connection_config = buildConnection(ptype, fields);
      await createResourceConfig({
        id: form.id || undefined,
        name: form.name,
        type: ptype,
        description: form.description,
        connection_config,
        enabled: true,
      });
      setForm({ id: "", name: "", description: "" });
      setFields(emptyFields(ptype));
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
        <p>
          平台级「连接器」：按类型填写连接与策略字段，供工作流里 Agent 绑定（resource_ids）。应用内的项目资源（线索、指标口径）在
          <strong> 应用详情 → 应用资源 </strong>
          中维护。
        </p>
      </header>
      {error ? <div className="error">{error}</div> : null}
      <div className="grid two">
        <SectionCard title="新增平台资源">
          <form className="form resource-registry-form" onSubmit={(e) => void handleSubmit(e)}>
            <label>
              ID（可选，留空自动生成）
              <input value={form.id} onChange={(event) => setForm({ ...form, id: event.target.value })} />
            </label>
            <label>
              名称
              <input
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                required
              />
            </label>
            <label>
              类型
              <select value={ptype} onChange={(e) => changeType(e.target.value as PlatformResourceType)}>
                {TYPE_OPTIONS.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            <p className="muted" style={{ margin: "-6px 0 4px", fontSize: "13px" }}>
              {TYPE_OPTIONS.find((t) => t.id === ptype)?.hint}
            </p>
            <label>
              描述
              <input
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
              />
            </label>
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
            <button type="submit">保存资源</button>
          </form>
        </SectionCard>
        <SectionCard title="已注册资源">
          <ul className="list resource-registry-list">
            {resources.map((resource) => (
              <li key={resource.id}>
                <span className="resource-type-pill">{resource.type}</span>
                <div>
                  <strong>{resource.name}</strong>
                  <p className="muted">{resource.description || "无描述"}</p>
                  <p className="muted" style={{ fontSize: "12px" }}>
                    连接摘要：{summarizeConnection(resource)}
                  </p>
                </div>
                <code style={{ fontSize: "11px", alignSelf: "start" }}>{resource.id}</code>
              </li>
            ))}
          </ul>
        </SectionCard>
      </div>
    </div>
  );
}
